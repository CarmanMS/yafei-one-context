"""Schema tests for skill_config and scenario_config."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from one_context.eval.skill_config import load_skill_eval, SkillEvalConfig
from one_context.eval.scenario_config import load_scenario, ScenarioConfig


def test_skill_eval_defaults_when_missing(tmp_path: Path) -> None:
    cfg = load_skill_eval(tmp_path)
    assert cfg.judge_model.startswith("claude-haiku")
    assert cfg.artifacts == []
    assert cfg.default_rubric == ""


def test_skill_eval_parses_yaml(tmp_path: Path) -> None:
    (tmp_path / "eval.yaml").write_text(
        "description: t\n"
        "judge_model: m\n"
        "artifacts: ['a/**', 'b.md']\n"
        "default_rubric: |\n"
        "  rule one\n",
        encoding="utf-8",
    )
    cfg = load_skill_eval(tmp_path)
    assert cfg.judge_model == "m"
    assert cfg.artifacts == ["a/**", "b.md"]
    assert "rule one" in cfg.default_rubric


def test_skill_eval_extra_field_rejected(tmp_path: Path) -> None:
    (tmp_path / "eval.yaml").write_text(
        "judge_model: m\nbogus: 1\n", encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_skill_eval(tmp_path)


def test_scenario_provider_cwd_rejected(tmp_path: Path) -> None:
    """ISS-012: provider.cwd must be rejected."""
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\n"
        "target_path: x/\n"
        "provider:\n"
        "  cwd: should-not-be-here\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="provider.cwd is not allowed"):
        load_scenario(scn)


def test_scenario_minimal_valid(tmp_path: Path) -> None:
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: features/foo/\n",
        encoding="utf-8",
    )
    cfg = load_scenario(scn)
    assert cfg.query == "q"
    assert cfg.target_path == "features/foo/"
    # legacy alias mirrored for backward-compat readers
    assert cfg.cwd == "features/foo/"
    assert cfg.repeat == 1
    assert cfg.threshold == 0.8
    # ISS-022: overlay is OPTIONAL (defaults to None when omitted)
    assert cfg.overlay is None


def test_scenario_repeat_must_be_positive(tmp_path: Path) -> None:
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: x/\nrepeat: 0\n", encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_scenario(scn)


def test_scenario_threshold_in_range(tmp_path: Path) -> None:
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: x/\nthreshold: 1.5\n", encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_scenario(scn)


def test_scenario_full_example_parses(tmp_path: Path) -> None:
    """ISS-022: full example uses the new `overlay.apply:` block."""
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "description: full\n"
        "query: hello\n"
        "target_path: features/foo/\n"
        "overlay:\n"
        "  apply:\n"
        "    - src: patches/spec-override.md\n"
        "      dst: '{{ target_path }}spec.md'\n"
        "provider:\n"
        "  model: claude-sonnet-4-5\n"
        "  permissionMode: bypassPermissions\n"
        "  timeoutMs: 60000\n"
        "repeat: 3\n"
        "rubric: hi\n"
        "threshold: 0.7\n"
        "artifacts_override:\n"
        "  - production/cover/**\n"
        "include_git: true\n",
        encoding="utf-8",
    )
    cfg = load_scenario(scn)
    assert cfg.overlay is not None
    assert cfg.overlay.apply[0].src == "patches/spec-override.md"
    assert cfg.overlay.apply[0].dst == "{{ target_path }}spec.md"
    assert cfg.repeat == 3
    assert cfg.threshold == 0.7
    assert cfg.artifacts_override == ["production/cover/**"]
    assert cfg.include_git is True


# ─────────────────────────────────────────────────────────────────────
# ISS-020 compat layer: cwd → target_path migration
# ─────────────────────────────────────────────────────────────────────

def test_scenario_target_path_only_no_warning(tmp_path: Path) -> None:
    """Pure new-style: only target_path set, no DeprecationWarning."""
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: features/foo/\n", encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = load_scenario(scn)
    # no DeprecationWarning fired
    assert not any(
        issubclass(wi.category, DeprecationWarning) for wi in w
    ), f"unexpected DeprecationWarnings: {[str(x.message) for x in w]}"
    assert cfg.target_path == "features/foo/"


def test_scenario_legacy_cwd_emits_warning_and_routes(tmp_path: Path) -> None:
    """Only legacy `cwd`: warn + auto-route into target_path."""
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ncwd: features/foo/\n", encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = load_scenario(scn)
    dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert dep, "expected DeprecationWarning for legacy cwd"
    assert "deprecated" in str(dep[0].message).lower()
    assert cfg.target_path == "features/foo/"
    assert cfg.cwd == "features/foo/"


def test_scenario_both_cwd_and_target_path_warns_and_prefers_target_path(
    tmp_path: Path,
) -> None:
    """Both set: warn (cwd ignored) and prefer target_path."""
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\n"
        "target_path: features/new/\n"
        "cwd: features/old/\n",
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = load_scenario(scn)
    dep = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert dep, "expected DeprecationWarning when both fields set"
    assert "ignored" in str(dep[0].message).lower() or "both" in str(dep[0].message).lower()
    assert cfg.target_path == "features/new/"
    # cwd is overwritten to mirror target_path for backward compat
    assert cfg.cwd == "features/new/"


def test_scenario_neither_cwd_nor_target_path_raises(tmp_path: Path) -> None:
    """Neither field set: ValidationError / ValueError with clear message."""
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text("query: q\n", encoding="utf-8")
    with pytest.raises(Exception, match="target_path"):
        load_scenario(scn)


# ── Phase 2.6.B: declarative assertions schema ─────────────────────────────


def test_skill_eval_parses_assertions(tmp_path: Path) -> None:
    (tmp_path / "eval.yaml").write_text(
        "default_rubric: |\n"
        "  fall back rubric\n"
        "assertions:\n"
        "  - id: file-01\n"
        "    kind: file_exists\n"
        "    path: production/01.json\n"
        "  - id: scores-in-range\n"
        "    kind: json_field\n"
        "    path: production/03.json\n"
        "    field: $[*].total_score\n"
        "    op: in_range\n"
        "    min: 0\n"
        "    max: 100\n",
        encoding="utf-8",
    )
    cfg = load_skill_eval(tmp_path)
    assert len(cfg.assertions) == 2
    assert cfg.assertions[0].id == "file-01"
    assert cfg.assertions[0].kind == "file_exists"
    assert cfg.assertions[1].op == "in_range"
    assert cfg.assertions[1].min == 0
    assert cfg.assertions[1].max == 100


def test_skill_eval_assertion_unknown_kind_rejected(tmp_path: Path) -> None:
    (tmp_path / "eval.yaml").write_text(
        "assertions:\n"
        "  - id: x\n"
        "    kind: bogus_kind\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_skill_eval(tmp_path)


def test_skill_eval_assertion_extra_field_rejected(tmp_path: Path) -> None:
    """`extra=forbid` on AssertionSpec catches typos like `pat:` for `path:`."""
    (tmp_path / "eval.yaml").write_text(
        "assertions:\n"
        "  - id: x\n"
        "    kind: file_exists\n"
        "    pat: production/oops.json\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_skill_eval(tmp_path)


def test_scenario_assertions_and_skip_parse(tmp_path: Path) -> None:
    scn = tmp_path / "s"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\n"
        "target_path: features/foo/\n"
        "assertions_skip:\n"
        "  - default-from-skill\n"
        "assertions:\n"
        "  - id: scn-extra\n"
        "    kind: text_contains\n"
        "    source: file\n"
        "    path: production/04.md\n"
        "    needle: 'Step 6 在评测模式下跳过'\n",
        encoding="utf-8",
    )
    cfg = load_scenario(scn)
    assert cfg.assertions_skip == ["default-from-skill"]
    assert len(cfg.assertions) == 1
    assert cfg.assertions[0].id == "scn-extra"
    assert cfg.assertions[0].needle == "Step 6 在评测模式下跳过"


def test_scenario_assertion_id_collision_with_skill_raises_at_merge() -> None:
    """Schema layer accepts both lists; collision is detected at runner-level
    `merge_assertions`. This test pins that contract."""
    from one_context.eval.assertions import (
        AssertionSpec,
        merge_assertions,
    )
    skill = [AssertionSpec(id="a", kind="file_exists", path="x")]
    scenario = [AssertionSpec(id="a", kind="file_exists", path="y")]
    with pytest.raises(ValueError, match="collides"):
        merge_assertions(skill, scenario, [])
    # but `assertions_skip: [a]` resolves it
    out = merge_assertions(skill, scenario, ["a"])
    assert len(out) == 1 and out[0].path == "y"
