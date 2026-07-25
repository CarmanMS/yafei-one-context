"""Pydantic schema for `skills/<name>/evals/<scenario>/scenario.yaml`.

ISS-012: `provider.cwd` field is REJECTED — cwd is single-source from
the runner, which spawns provider with sandbox root as cwd.

ISS-020 / Stage 2.0.2: the scenario-level `cwd` field is being renamed
to `target_path`. The old `cwd` name is still accepted during the
transition window but emits a DeprecationWarning; after 2026-06-15 it
will raise.

ISS-022 / Stage 2.0.3: the legacy `fixture:` block (whole-subtree overlay
with `mode` / `apply` semantics) is REMOVED. Fixtures live under
`features/_evals/<category>/<feature-id>/` and are referenced via
`target_path:`. An optional `overlay.apply:` block carries per-scenario
single-file patches on top of the shared fixture. Loading an old
`fixture:` block raises with a migration hint.

ISS-024 / Stage 2.7.A: an optional `session_inject:` block enables
Session File Injection — runner forges a cc session jsonl
(~/.claude/projects/<hash>/<id>.jsonl) before spawn and starts cc with
`--resume <id>`. cc sees the forged tool_use+tool_result history as
"already happened" and skips re-invoking the mocked tool. The block is
opt-in: omit it (or set `enabled: false`) and scenarios keep the v1
behaviour (`--no-session-persistence`, real tool calls). See
tech_design.md §4 and session-injection-spike-result.md.

The two fields have the SAME meaning: a path relative to the repo root
that points at the feature subtree the skill is supposed to operate on.
The runner's spawn cwd is ALWAYS the sandbox root (which equals the
repo root, since clonefile / git archive copy the whole tree). `query`
template may reference `{{ target_path }}` so prompts can name the
feature path explicitly without smuggling sandbox absolute paths.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from one_context.eval.assertions import AssertionSpec


class OverlayItem(BaseModel):
    """One single-file overlay patch entry (ISS-022).

    `dst` may contain `{{ target_path }}` which is interpolated against
    the scenario's `target_path` value at apply time (see
    `fixture.apply_overlay`).
    """
    model_config = ConfigDict(extra="forbid")
    src: str  # relative to scenario directory
    dst: str  # path inside sandbox; supports {{ target_path }} interpolation


class OverlayConfig(BaseModel):
    """Optional single-file overlay layer on top of `target_path` fixture."""
    model_config = ConfigDict(extra="forbid")
    apply: list[OverlayItem] = Field(default_factory=list)


class SessionInjectConfig(BaseModel):
    """Session File Injection — v2 fixture main path (ISS-024 / Stage 2.7).

    When `enabled=True`, the runner reads `mock_rounds_dir` (relative to
    the scenario directory), forges a cc session jsonl file under
    `~/.claude/projects/<realpath(sandbox_root) → hash>/`, and spawns cc
    with `--resume <forged_session_id>`. cc treats the forged
    (assistant tool_use, user tool_result) pairs as past history and will
    NOT re-invoke the mocked tools — see tech_design.md §4.

    `schema_version` pins the expected cc CLI version. The runner compares
    it against the live `claude --version`; mismatch warns (does not block)
    so that authors get a heads-up when cc upgrades drift the jsonl
    schema. None defers to whatever the runner detects at spawn time.
    """
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    mock_rounds_dir: str | None = None  # relative to scenario directory
    schema_version: str | None = None   # e.g. "2.1.156"; None = no pinning

    @model_validator(mode="after")
    def _require_dir_when_enabled(self) -> "SessionInjectConfig":
        if self.enabled and not (self.mock_rounds_dir and self.mock_rounds_dir.strip()):
            raise ValueError(
                "session_inject.enabled=true requires a non-empty "
                "session_inject.mock_rounds_dir (relative to the scenario "
                "directory). Set it to the folder that holds round-*.yaml "
                "files, e.g. 'mock_rounds/'."
            )
        return self


class ProviderConfig(BaseModel):
    """`provider.cwd` is rejected to make cwd single-source (ISS-012)."""
    model_config = ConfigDict(extra="forbid")

    # Stage 2.X.4: `model` is now optional. When omitted/null the runner
    # resolves it via settings_resolver.resolve_effective_model() —
    # typically reading `env.ANTHROPIC_MODEL` from the settings.json that
    # `claude --settings <path>` is using. Keep the field so debug overrides
    # remain trivial (`provider.model: GLM-5.1`).
    model: str | None = None
    permissionMode: str = "bypassPermissions"
    timeoutMs: int = 180_000

    @field_validator("model")
    @classmethod
    def _model_nonempty_if_set(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("provider.model must not be empty string (use null/omit to defer to settings)")
        return v

    @field_validator("permissionMode")
    @classmethod
    def _permission_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v


# ISS-020 deprecation: after this date the `cwd` alias will raise instead
# of warning. Kept as a module constant so the warning message stays in
# sync with whatever final cutover policy we land on.
CWD_DEPRECATED_AFTER = "2026-06-15"


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = ""
    query: str

    # ISS-020: `target_path` is the canonical name. `cwd` is the
    # deprecated alias kept until CWD_DEPRECATED_AFTER. The compat layer
    # in `_normalize_target_path` validator picks one of them and writes
    # the chosen value into `target_path`.
    #
    # We deliberately do NOT use `Field(deprecated=True)` for `cwd`:
    # pydantic v2 installs a descriptor for deprecated fields that
    # raises `AttributeError` on any subsequent set (even
    # `object.__setattr__`), which would prevent the compat normalizer
    # below from mirroring `target_path` into the legacy alias. The
    # DeprecationWarning is raised explicitly instead.
    target_path: str | None = None
    cwd: str | None = None

    overlay: OverlayConfig | None = None
    session_inject: SessionInjectConfig | None = None  # ISS-024 / Stage 2.7
    provider: ProviderConfig = Field(default_factory=ProviderConfig)

    repeat: int = 1
    rubric: str = ""
    threshold: float = 0.8
    artifacts_override: list[str] | None = None
    include_git: bool = False

    # Phase 2.6.B: declarative assertions. `assertions` is additive on top
    # of the skill defaults; `assertions_skip` reverse-disables a skill
    # default by `id` (use this before redeclaring with the same id).
    assertions: list[AssertionSpec] = Field(default_factory=list)
    assertions_skip: list[str] = Field(default_factory=list)

    # ── Stage 2.0.1 (sandbox driver, ISS-021) — both optional & independent ──
    # `sandbox_driver`: pin a specific isolation driver (debug / cross-platform
    #     reproducibility). When None, runner runs `sandbox._detect_driver()`.
    # `sandbox_includes`: extra git-archive pathspecs. Only honoured when the
    #     effective driver is `git_archive`; clonefile / reflink ignore it
    #     (whole-repo COW is already free — see tech_design §2.7).
    sandbox_driver: Literal[
        "apfs_clonefile", "linux_reflink", "git_archive"
    ] | None = None
    sandbox_includes: list[str] | None = None

    @field_validator("repeat")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("repeat must be >= 1")
        return v

    @field_validator("threshold")
    @classmethod
    def _ratio(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be in [0.0, 1.0]")
        return v

    @model_validator(mode="after")
    def _normalize_target_path(self) -> "ScenarioConfig":
        """ISS-020 compat: route `cwd` → `target_path` with deprecation.

        Stage 2.0.3 note: pydantic v2 `Field(..., deprecated=True)` installs
        a `_DeprecatedFieldDescriptor` that refuses every write — including
        `object.__setattr__`. We bypass it via `__dict__` so the compat
        layer can mirror values without re-triggering the deprecation
        descriptor.
        """
        if self.target_path and self.cwd:
            warnings.warn(
                "scenario.yaml: both 'target_path' and 'cwd' are set; "
                "'cwd' is deprecated and will be ignored. "
                f"After {CWD_DEPRECATED_AFTER} the 'cwd' alias will raise.",
                DeprecationWarning,
                stacklevel=2,
            )
            # `cwd` ignored; keep target_path as-is.
            self.__dict__["cwd"] = self.target_path
            return self
        if self.target_path and not self.cwd:
            # mirror canonical value into cwd alias for backward-compat
            # readers (run.json keeps writing both for now).
            self.__dict__["cwd"] = self.target_path
            return self
        if not self.target_path and self.cwd:
            warnings.warn(
                "scenario.yaml: 'cwd' is deprecated, please use 'target_path' "
                f"instead. After {CWD_DEPRECATED_AFTER} this will raise.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.__dict__["target_path"] = self.cwd
            return self
        # neither set
        raise ValueError(
            "scenario.yaml: missing required field 'target_path' "
            "(the deprecated alias 'cwd' is also accepted during the "
            f"transition; deadline {CWD_DEPRECATED_AFTER})."
        )


def load_scenario(scenario_dir: Path) -> ScenarioConfig:
    """Load `<scenario_dir>/scenario.yaml` and reject unknown fields."""
    path = scenario_dir / "scenario.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"missing scenario.yaml: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping at top level")
    # ISS-012: reject `provider.cwd` early with a clear message
    prov = raw.get("provider")
    if isinstance(prov, dict) and "cwd" in prov:
        raise ValueError(
            f"{path}: provider.cwd is not allowed — cwd is single-source from "
            f"the top-level `target_path` field (ISS-012). Remove provider.cwd."
        )
    # ISS-022: reject legacy `fixture:` block with a migration hint
    if "fixture" in raw:
        raise ValueError(
            f"{path}: legacy `fixture:` block is no longer supported "
            f"(ISS-022). Migrate the fixture subtree into "
            f"`features/_evals/<category>/<feature-id>/`, point `target_path:` "
            f"at it, and use `overlay.apply:` for per-scenario single-file "
            f"patches."
        )
    return ScenarioConfig.model_validate(raw)
