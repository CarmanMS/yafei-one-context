"""commit_finalize — recorder Stage B (Phase 2.8 M4).

Turns the M3 `staging/` artifacts + user feedback into the final
`skills/<skill>/evals/<scenario>/{scenario.yaml, mock_rounds/, baseline/,
judge_prompt.md, assertions/recorded.yaml}` deliverable + releases the
session lock.

Pipeline:

1. Load session, assert status == "finalizing"
2. Parse staging/judge_candidates_draft.md → set of D/F ids + draft query
3. LLM-parse user_feedback_md → {keep, drop, overrides, query, target_path}
   - LLM failure → CommitFailure (session stays finalizing; staging untouched)
   - ambiguous_intents non-empty → return user_clarification (no rollback)
   - unknown ids → InvalidFinalizeFeedback (no rollback)
4. Validate target_path: required (from feedback OR ask user) + must exist
   under repo_root → compute sha256, fill into baseline/meta.json
5. Validate query: required (from feedback OR draft) → reject if both empty
6. Build judge_prompt.md from kept D/F sections + threshold overrides
7. Build assertions/recorded.yaml:
   - extract objective DSL candidates from draft (none yet — M5 hands judge
     the work; M4 only auto-generates the P3 double-insurance tool_call_count
     entries — design §12.3)
   - auto-append `tool_call_count == 0` blocking assertion for every
     tool_name that appeared in staging/mock_rounds/
8. Build scenario.yaml (§3.5 schema) — inline assertions because
   scenario_config.py uses safe_load (no `!include` constructor)
9. Run ScenarioConfig.model_validate on the produced scenario.yaml; if
   it fails, raise — never leave a broken scenario on disk
10. ScenarioDirConflict handling: target dir non-empty + overwrite=False
    raises; overwrite=True backs up to <scenario_dir>.bak.<ts>
11. Atomic move staging → target via shutil.move (cross-fs aware)
12. Mark session committed, clear active.json, rmtree staging only (keep
    session.json for post-commit audit; load_session(sid) still works)
13. Return {scenario_dir, files_written, warnings, scenario_yaml_path}
    where warnings carries any staging/warnings.txt content forward
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from one_context.eval.assertions import AssertionSpec
from one_context.eval.scenario_config import ScenarioConfig
from one_context.eval.session_inject import MockRound
from one_context.recorder import llm_client
from one_context.recorder.prompts import render_prompt
from one_context.recorder.session import (
    RecorderError,
    Session,
    SessionWrongState,
    _active_file,
    load_session,
    recorder_root,
    resolve_repo_root,
    save_session,
)


# ── error types ────────────────────────────────────────────────────────


class CommitFailure(RecorderError):
    """LLM call failed (parse error / spawn error). Staging preserved."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {message}")


class InvalidFinalizeFeedback(RecorderError):
    """User referenced D/F ids that don't exist in the candidate draft."""

    def __init__(self, unknown_ids: list[str]) -> None:
        self.unknown_ids = unknown_ids
        super().__init__(
            f"user feedback references unknown D/F ids: "
            f"{', '.join(unknown_ids)}; check the candidate draft for "
            f"valid ids"
        )


class TargetPathNotFound(RecorderError):
    def __init__(self, target_path: str, repo_root: Path) -> None:
        self.target_path = target_path
        super().__init__(
            f"target_path {target_path!r} does not exist under repo root "
            f"{repo_root}; provide an existing path or create the fixture "
            f"subtree first"
        )


class EmptyTargetPath(RecorderError):
    """target_path resolves to an empty directory (no files inside).

    Almost always means target_path was misconfigured — e.g. self-referencing
    the scenario directory, or pointing at a placeholder before the fixture
    was populated. The original silent behaviour returned `sha256("")` =
    e3b0c44...b855 and let the broken scenario commit anyway, which hid the
    misconfiguration until replay produced confusing results.
    """

    def __init__(self, target_path: str, abs_path: Path) -> None:
        self.target_path = target_path
        super().__init__(
            f"target_path {target_path!r} resolves to {abs_path} but contains "
            f"no files; this almost always means target_path is misconfigured "
            f"(e.g. self-references the scenario dir, or fixture not seeded). "
            f"Point it at the real input subtree before committing."
        )


class ScenarioDirConflict(RecorderError):
    def __init__(self, existing: Path) -> None:
        self.existing = existing
        super().__init__(
            f"scenario directory {existing} is non-empty; re-run with "
            f"overwrite=True to back it up to <dir>.bak.<ts> and replace"
        )


# ── candidate-draft parser ─────────────────────────────────────────────

# `### D1: name` / `### F2: name` heading + body until the next `###` or `##`
_HEADING_RE = re.compile(r"^###\s+([DF]\d+):\s*(.*?)\s*$", re.MULTILINE)
_WEIGHT_RE = re.compile(r"\*\*权重\*\*\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)")
_COVERS_RE = re.compile(r"\*\*covers\*\*\s*[:：]\s*\[([^\]]*)\]")
_PASS_THRESHOLD_RE = re.compile(r"pass_threshold\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)")
_QUERY_SECTION_RE = re.compile(
    r"##\s*候选\s*query\s*\n+(.*?)(?=\n##\s|\Z)",
    re.DOTALL,
)


@dataclass
class CandidateItem:
    id: str                  # "D1" / "F2"
    name: str
    body: str                # full markdown body after the heading
    weight: float | None     # only meaningful for D items
    covers: list[str]        # F-NN ids it covers (for reporting)


@dataclass
class ParsedDraft:
    items: dict[str, CandidateItem]  # keyed by "D1" / "F1" / ...
    candidate_query: str             # text from `## 候选 query` section
    pass_threshold: float            # default 0.7 when absent
    raw: str


def _parse_candidate_draft(md: str) -> ParsedDraft:
    """Parse the candidate-list markdown into structured items.

    The draft format follows finalize_judge_draft.md template:
        ### D1: <name>
        **判定标准**: ...
        **权重**: 0.5
        **covers**: [F-01, F-02]
        ### D2: ...
        ### F1: <name>
        **特征**: ...
        **covers**: [F-03]
        ...
        ## 总分阈值
        `pass_threshold: 0.7`

    Unknown sections are kept verbatim in the item's `body` so the
    judge_prompt.md emitter can paste them back; we only structurally
    extract weight + covers + threshold.
    """
    headings = list(_HEADING_RE.finditer(md))
    items: dict[str, CandidateItem] = {}
    for i, m in enumerate(headings):
        item_id = m.group(1)
        name = m.group(2).strip()
        body_start = m.end()
        body_end = (
            headings[i + 1].start() if i + 1 < len(headings) else len(md)
        )
        # Trim body at the next `## ` (any H2) so we don't bleed into the
        # next major section like "## 总分阈值".
        body = md[body_start:body_end]
        next_h2 = re.search(r"^##\s", body, re.MULTILINE)
        if next_h2:
            body = body[: next_h2.start()]
        body = body.strip()

        wm = _WEIGHT_RE.search(body)
        weight = float(wm.group(1)) if wm else None
        cm = _COVERS_RE.search(body)
        covers: list[str] = []
        if cm:
            covers = [
                tok.strip().strip("'\"") for tok in cm.group(1).split(",")
                if tok.strip()
            ]
        items[item_id] = CandidateItem(
            id=item_id, name=name, body=body,
            weight=weight, covers=covers,
        )

    # query section
    candidate_query = ""
    qm = _QUERY_SECTION_RE.search(md)
    if qm:
        candidate_query = qm.group(1).strip()
        # strip lone "TBD: ..." sentinel writers leave when no obvious query
        if candidate_query.startswith("TBD") or candidate_query == "(none captured)":
            candidate_query = ""

    # pass_threshold
    pm = _PASS_THRESHOLD_RE.search(md)
    pass_threshold = float(pm.group(1)) if pm else 0.7

    return ParsedDraft(
        items=items, candidate_query=candidate_query,
        pass_threshold=pass_threshold, raw=md,
    )


# ── feedback LLM parser ────────────────────────────────────────────────


def _build_candidates_summary(draft: ParsedDraft) -> str:
    lines: list[str] = []
    if draft.candidate_query:
        lines.append(f"候选 query: {draft.candidate_query}")
    else:
        lines.append("候选 query: (无)")
    lines.append(f"默认 pass_threshold: {draft.pass_threshold}")
    lines.append("候选维度:")
    for key in sorted(draft.items.keys(), key=_sort_id_key):
        it = draft.items[key]
        wpart = f" weight={it.weight}" if it.weight is not None else ""
        cpart = f" covers={it.covers}" if it.covers else ""
        lines.append(f"  - {it.id}: {it.name}{wpart}{cpart}")
    return "\n".join(lines)


def _sort_id_key(s: str) -> tuple[int, int]:
    # Sort D before F, then numerically.
    head = 0 if s.startswith("D") else 1
    try:
        n = int(s[1:])
    except ValueError:
        n = 9999
    return (head, n)


def _parse_feedback_via_llm(
    *, user_feedback_md: str, draft: ParsedDraft,
) -> dict:
    """Call recorder LLM to structure the user's free-text feedback.

    Returns a dict matching commit_feedback_parse.md schema. Raises
    CommitFailure on any LLM / JSON-parse error; caller decides whether
    to roll back staging.
    """
    prompt = render_prompt(
        "commit_feedback_parse.md",
        candidates_summary=_build_candidates_summary(draft),
        user_feedback_md=user_feedback_md or "(空反馈)",
    )
    try:
        raw = llm_client.call_llm_for_draft(prompt)
    except llm_client.LLMCallError as e:
        raise CommitFailure(
            "llm_parse_error",
            f"LLM call failed while parsing feedback: {e}",
        ) from e

    # Best-effort: strip any ```json fences the model might still emit
    # despite the prompt's `不要 markdown 代码块包裹` instruction.
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise CommitFailure(
            "llm_parse_error",
            f"LLM output was not valid JSON: {e}; raw head="
            f"{text[:200]!r}",
        ) from e
    if not isinstance(parsed, dict):
        raise CommitFailure(
            "llm_parse_error",
            f"LLM output was not a JSON object (got "
            f"{type(parsed).__name__})",
        )

    # Normalise — guarantee every field exists with the right type so
    # downstream code doesn't need to .get(...) defensively.
    return _normalise_parsed_feedback(parsed)


def _normalise_parsed_feedback(parsed: dict) -> dict:
    def _as_list(v: Any) -> list:
        return list(v) if isinstance(v, list) else []

    def _as_dict(v: Any) -> dict:
        return dict(v) if isinstance(v, dict) else {}

    return {
        "keep_dimensions": [str(x) for x in _as_list(parsed.get("keep_dimensions"))],
        "drop_dimensions": [str(x) for x in _as_list(parsed.get("drop_dimensions"))],
        "threshold_overrides": _as_dict(parsed.get("threshold_overrides")),
        "new_negative_cases": _as_list(parsed.get("new_negative_cases")),
        "query": (
            parsed.get("query").strip() if isinstance(parsed.get("query"), str)
            and parsed.get("query").strip() else None
        ),
        "target_path": (
            parsed.get("target_path").strip()
            if isinstance(parsed.get("target_path"), str)
            and parsed.get("target_path").strip() else None
        ),
        "ambiguous_intents": [str(x) for x in _as_list(parsed.get("ambiguous_intents"))],
    }


# ── id validation ──────────────────────────────────────────────────────


def _validate_ids(
    feedback: dict, draft: ParsedDraft,
) -> None:
    known = set(draft.items.keys())
    referenced = set(feedback["keep_dimensions"]) | set(feedback["drop_dimensions"])
    # threshold_overrides keys may carry id-prefixed weights (e.g. "D1.weight")
    for key in feedback["threshold_overrides"].keys():
        if "." in key:
            referenced.add(key.split(".", 1)[0])
    unknown = sorted(x for x in referenced if x not in known)
    if unknown:
        raise InvalidFinalizeFeedback(unknown)


# ── target_path sha256 ────────────────────────────────────────────────


def _target_path_sha256(repo_root: Path, target_path: str) -> str:
    """Hash a target_path subtree (or file) deterministically.

    For a single file: sha256(file_bytes). For a directory: sha256 of
    sorted "<rel_path>:<file_sha256>\\n" lines, mirroring how
    `git status --porcelain` style hashes are stable across same-content
    different-mtime trees. This is what M5 will compare against during
    replay to detect baseline drift.

    Raises:
        TargetPathNotFound: abs_path does not exist (defence-in-depth;
            caller already checks, but a backup/move between the check
            and this call would otherwise produce a silent empty hash).
        EmptyTargetPath: abs_path is a directory with no files — see
            class docstring for why this used to silently return
            sha256("") = e3b0c44... and what that masked.
    """
    abs_path = repo_root / target_path
    if not abs_path.exists():
        raise TargetPathNotFound(target_path, repo_root)
    if abs_path.is_file():
        return hashlib.sha256(abs_path.read_bytes()).hexdigest()
    # directory
    files = sorted(p for p in abs_path.rglob("*") if p.is_file())
    if not files:
        raise EmptyTargetPath(target_path, abs_path)
    h = hashlib.sha256()
    for f in files:
        rel = f.relative_to(abs_path).as_posix()
        fh = hashlib.sha256(f.read_bytes()).hexdigest()
        h.update(f"{rel}:{fh}\n".encode("utf-8"))
    return h.hexdigest()


# ── judge_prompt.md emission ──────────────────────────────────────────


def _build_judge_prompt(
    *,
    session: Session,
    draft: ParsedDraft,
    kept_ids: list[str],
    threshold_overrides: dict,
    new_negative_cases: list[dict],
    success_rationale: str,
) -> str:
    """Render the final judge_prompt.md per §3.4 schema.

    Kept D items go under `## 判定维度`; kept F items under `## 虚假通过反例`.
    Per-item weight overrides (`D1.weight`) are applied; final block
    carries `pass_threshold` (possibly overridden).
    """
    sorted_ids = sorted(kept_ids, key=_sort_id_key)
    d_items = [draft.items[i] for i in sorted_ids if i.startswith("D")]
    f_items = [draft.items[i] for i in sorted_ids if i.startswith("F")]

    lines: list[str] = []
    lines.append(f"# Judge Prompt — {session.skill_name} / {session.scenario_name}")
    lines.append("")
    lines.append("## 这次录制为什么算成功")
    lines.append("")
    lines.append(success_rationale.strip() or "(请人工补充)")
    lines.append("")
    lines.append("## 判定维度（LLM 给 0-1 分）")
    lines.append("")
    if not d_items:
        lines.append("(本次未保留任何判定维度)")
        lines.append("")
    for it in d_items:
        weight = it.weight if it.weight is not None else 0.5
        override_key = f"{it.id}.weight"
        if override_key in threshold_overrides:
            try:
                weight = float(threshold_overrides[override_key])
            except (TypeError, ValueError):
                pass
        lines.append(f"### {it.id}: {it.name}")
        # Re-emit the item body verbatim, but rewrite **权重** to the
        # possibly-overridden value so the user sees one weight only.
        body = _rewrite_weight_in_body(it.body, weight)
        lines.append(body)
        lines.append("")
    lines.append("## 虚假通过反例（出现任一即 FAIL）")
    lines.append("")
    if not f_items and not new_negative_cases:
        lines.append("(本次未保留任何反例)")
        lines.append("")
    for it in f_items:
        lines.append(f"### {it.id}: {it.name}")
        lines.append(it.body)
        lines.append("")
    for nc in new_negative_cases:
        nid = str(nc.get("id", "F-XX"))
        feature = str(nc.get("feature", "")).strip()
        source_hint = str(nc.get("source_hint", "")).strip()
        lines.append(f"### {nid}: {feature[:60]}")
        if feature:
            lines.append(f"**特征**：{feature}")
        if source_hint:
            lines.append(f"**反例数据来源**：{source_hint}")
        lines.append("")

    threshold = threshold_overrides.get(
        "pass_threshold", draft.pass_threshold
    )
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        threshold = draft.pass_threshold
    lines.append("## 总分阈值")
    lines.append("")
    lines.append(f"`pass_threshold: {threshold}`（加权和）")
    lines.append("")
    return "\n".join(lines)


def _rewrite_weight_in_body(body: str, weight: float) -> str:
    """Replace any `**权重**：X` line with the resolved value."""
    repl = f"**权重**：{weight}"
    new, n = _WEIGHT_RE.subn(repl, body)
    if n == 0:
        # body had no weight line; append one so the final prompt always
        # documents the weight (matters when M5 judge parses it back).
        new = body.rstrip() + f"\n{repl}\n"
    return new


# ── assertions/recorded.yaml emission ─────────────────────────────────


def _collect_tool_names_from_mock_rounds(mock_rounds_dir: Path) -> list[str]:
    """Return sorted unique tool_name set across staging mock_rounds yaml.

    Drives the design §12.3 P3 double-insurance: every external tool the
    skill called during recording earns a `tool_call_count == 0` blocking
    assertion so the replay run cannot silently make the *real* call (cc
    "escapes" the forged session history).
    """
    if not mock_rounds_dir.is_dir():
        return []
    seen: set[str] = set()
    for f in sorted(mock_rounds_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(raw, dict):
            tn = raw.get("tool_name")
            if isinstance(tn, str) and tn.strip():
                seen.add(tn.strip())
    return sorted(seen)


def _build_p3_double_insurance_assertions(tool_names: list[str]) -> list[dict]:
    """One blocking tool_call_count(tool_name)==0 entry per external tool.

    Per design §12.3: pairs with the runner's --disallowedTools cc arg
    (added in M5). Either layer failing alone is a FAIL; both layers
    passing means cc honoured the forged history and didn't try a real
    call.
    """
    out: list[dict] = []
    for tn in tool_names:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", tn).strip("-").lower() or "tool"
        out.append({
            "id": f"no-real-{slug}-escape",
            "kind": "tool_call_count",
            "blocking": True,
            "tool_name": tn,
            "count_min": 0,
            "count_max": 0,
            "message": (
                f"session inject 应让 cc 跳过真 {tn} 调用；若出现 ≥1 次即视为"
                "cc 逃逸 session inject（design §12.3 双保险）"
            ),
        })
    return out


def _validate_assertions_list(asserts: list[dict]) -> None:
    """Round-trip every assertion through AssertionSpec.model_validate.

    Raises ValueError aggregating all failures (so the user sees the full
    diff in one shot instead of fix-one-at-a-time).
    """
    errors: list[str] = []
    for i, entry in enumerate(asserts):
        try:
            AssertionSpec.model_validate(entry)
        except Exception as e:  # pragma: no cover - defensive
            errors.append(f"assertions[{i}] (id={entry.get('id')!r}): {e}")
    if errors:
        raise ValueError(
            "generated assertions failed schema validation:\n"
            + "\n".join(errors)
        )


# ── scenario.yaml emission ────────────────────────────────────────────


def _build_scenario_yaml(
    *,
    query: str,
    target_path: str,
    threshold: float,
    assertions: list[dict],
    rubric: str = "",
) -> dict:
    """Compose the scenario.yaml mapping for M4.

    Deviations from design §3.5 spec:

    1. `assertions` are inlined (not `!include`) — scenario_config.py
       uses bare `yaml.safe_load` so the `!include` tag would crash the
       loader. The companion `assertions/recorded.yaml` is still written
       as a human-readable copy. (§10 new finding for M5/v3.)
    2. No `judge:` block — ScenarioConfig has no `judge` field yet so a
       block here would fail validation. `threshold` is at the top level
       (already supported); M5 can convention-discover `judge_prompt.md`
       by filename, or extend ScenarioConfig to accept `judge:`. (§10
       new finding for M5/v3.)

    R-8 治理 (design §16.7.10): `rubric` is the judge_prompt.md content
    inlined into `scenario.yaml`. ScenarioConfig.rubric (a `str` field
    on the model) is read by runner.judge_mod.merge_rubric; without
    this the recorded scenario produces "no rubric configured" judge
    fails. Default "" preserves M4 backward compat for callers that
    don't pass it.
    """
    out: dict = {
        "query": query,
        "target_path": target_path,
        "session_inject": {
            "enabled": True,
            "mock_rounds_dir": "mock_rounds/",
        },
        "assertions": assertions,
        "threshold": threshold,
    }
    if rubric and rubric.strip():
        # Place rubric last so the rest of the yaml stays readable up-top
        # (rubric is often hundreds of lines). yaml.safe_dump uses
        # default_flow_style=False at the call site, so multi-line rubric
        # serializes as a literal block.
        out["rubric"] = rubric
    return out


def _validate_scenario_yaml(scenario_yaml: dict, scenario_dir: Path) -> None:
    """Round-trip the produced mapping through ScenarioConfig.model_validate.

    Catches our own emitter bugs before the file lands on disk; the M5
    runner reuses the same loader path, so passing here implies the
    scenario will load at replay time.
    """
    try:
        ScenarioConfig.model_validate(scenario_yaml)
    except Exception as e:
        raise ValueError(
            f"generated scenario.yaml failed ScenarioConfig validation: {e}"
        ) from e


# ── physical move staging → target ────────────────────────────────────


def _backup_existing(target: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = target.parent / f"{target.name}.bak.{ts}"
    # Avoid bak collision (multiple commits within 1s on same scenario).
    n = 0
    while bak.exists():
        n += 1
        bak = target.parent / f"{target.name}.bak.{ts}-{n}"
    shutil.move(str(target), str(bak))
    return bak


def _move_staging_to_target(
    staging: Path, target: Path,
) -> None:
    """Move staging contents into target dir atomically as possible.

    Strategy: create target.parent if needed → if target exists, raise
    (caller already handled overwrite). Otherwise shutil.move the staging
    dir to target. shutil.move auto-falls-back to copy+remove when the
    source and dest are on different filesystems (tmpfs /tmp vs disk).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        # Caller responsible for backup; guard here is belt + suspenders.
        raise FileExistsError(
            f"refusing to overwrite existing scenario dir {target}"
        )
    shutil.move(str(staging), str(target))


def _list_files_recursive(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
    )


# ── repo_root resolution ───────────────────────────────────────────────


def _resolve_repo_root(explicit: Path | None) -> Path:
    """Wrapper kept for backwards compat; delegates to session helper."""
    return resolve_repo_root(explicit)


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _write_last_commit_outcome(
    staging: Path,
    *,
    outcome: str,
    error_class: str = "",
    message: str = "",
    ambiguous_intents: list[str] | None = None,
    questions: list[str] | None = None,
) -> None:
    """Persist the most recent non-success commit attempt for the report.

    `staging/` must already exist; this is best-effort — IO errors and
    missing staging are silently ignored so we never break the original
    error surface.
    """
    if not staging.is_dir():
        return
    payload: dict[str, Any] = {
        "outcome": outcome,
        "error_class": error_class,
        "message": message,
        "ts": _utc_now_iso(),
    }
    if ambiguous_intents:
        payload["ambiguous_intents"] = list(ambiguous_intents)
    if questions:
        payload["questions"] = list(questions)
    try:
        (staging / "last_commit_outcome.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

    try:
        from one_context.recorder import report as _report
        from one_context.recorder.session import load_session as _load
        # session_id is encoded in staging path: <root>/<session_id>/staging
        session_id = staging.parent.name
        try:
            session = _load(session_id)
        except Exception:
            return
        _report.render_staging(session)
    except Exception:
        pass


# ── public entry ───────────────────────────────────────────────────────


def commit_finalize_session(
    session_id: str,
    user_feedback_md: str,
    *,
    overwrite: bool = False,
    repo_root: Path | None = None,
) -> dict:
    """Wrapper around `_commit_finalize_impl` that persists a
    `staging/last_commit_outcome.json` on any failure path (RecorderError
    subclasses + ValueError from schema validation). The next staging
    recording_report.html will surface it in the Diagnostics tab.

    See `_commit_finalize_impl` for the full pipeline.
    """
    try:
        return _commit_finalize_impl(
            session_id, user_feedback_md,
            overwrite=overwrite, repo_root=repo_root,
        )
    except (RecorderError, ValueError) as e:
        try:
            session = load_session(session_id)
            staging = session.dir / "staging"
        except Exception:
            staging = None
        if staging is not None:
            _write_last_commit_outcome(
                staging,
                outcome="failure",
                error_class=type(e).__name__,
                message=str(e),
            )
        raise


def _commit_finalize_impl(
    session_id: str,
    user_feedback_md: str,
    *,
    overwrite: bool = False,
    repo_root: Path | None = None,
) -> dict:
    """Run commit_finalize Stage B. Return summary dict.

    On `ambiguous_intents` from the LLM, returns
    `{"action": "user_clarification", "questions": [...]}` instead of
    raising — the caller should prompt the user for more detail and
    re-invoke. Staging is left untouched in that case.

    Raises:
        SessionWrongState: status != 'finalizing'
        CommitFailure: LLM failed to parse feedback
        InvalidFinalizeFeedback: feedback mentions unknown D/F ids
        TargetPathNotFound: provided target_path missing under repo_root
        ScenarioDirConflict: target dir non-empty + overwrite=False
        ValueError: scenario.yaml / assertions failed schema validation
    """
    session = load_session(session_id)
    if session.status != "finalizing":
        raise SessionWrongState(
            f"commit_finalize_session requires status='finalizing', got "
            f"{session.status!r} (session_id={session_id!r})"
        )
    rroot = _resolve_repo_root(repo_root)

    session_dir = session.dir
    staging = session_dir / "staging"
    if not staging.is_dir():
        raise SessionWrongState(
            f"session {session_id!r} has no staging dir at {staging}; "
            "did finalize run successfully?"
        )

    # 1. parse candidate draft
    draft_path = staging / "judge_candidates_draft.md"
    if not draft_path.is_file():
        raise SessionWrongState(
            f"missing {draft_path}; finalize must precede commit_finalize"
        )
    draft = _parse_candidate_draft(draft_path.read_text(encoding="utf-8"))
    if not draft.items:
        raise SessionWrongState(
            f"candidate draft has no D/F items; nothing to commit. "
            f"Edit {draft_path} or abort + re-record."
        )

    # 2. LLM-parse feedback (raises CommitFailure on LLM error)
    feedback = _parse_feedback_via_llm(
        user_feedback_md=user_feedback_md, draft=draft,
    )

    # 3. ambiguous → no rollback, ask user to clarify
    if feedback["ambiguous_intents"]:
        _write_last_commit_outcome(
            staging,
            outcome="user_clarification",
            error_class="ambiguous_intents",
            message="LLM parser flagged ambiguous intents; user must clarify.",
            ambiguous_intents=list(feedback["ambiguous_intents"]),
        )
        return {
            "action": "user_clarification",
            "questions": list(feedback["ambiguous_intents"]),
            "session_id": session_id,
        }

    # 4. unknown ids → fail-fast
    _validate_ids(feedback, draft)

    # 5. resolve query / target_path with feedback-then-draft precedence
    query = feedback["query"] or draft.candidate_query
    target_path = feedback["target_path"]
    missing: list[str] = []
    if not query:
        missing.append("query")
    if not target_path:
        missing.append("target_path")
    if missing:
        _write_last_commit_outcome(
            staging,
            outcome="user_clarification",
            error_class="missing_fields",
            message=f"required fields missing: {', '.join(missing)}",
            questions=[
                f"请在反馈里明确指定 {field}（draft 未给出候选/用户也未提供）"
                for field in missing
            ],
        )
        return {
            "action": "user_clarification",
            "questions": [
                f"请在反馈里明确指定 {field}（draft 未给出候选/用户也未提供）"
                for field in missing
            ],
            "session_id": session_id,
        }

    # 6. target_path must exist (recorder cannot guess)
    if "_recording" in Path(target_path).parts:
        raise RecorderError(
            f"target_path {target_path!r} is reserved: the segment "
            "'_recording' is used by recording_report.html and must not "
            "appear in scenario inputs."
        )
    abs_target = rroot / target_path
    if not abs_target.exists():
        raise TargetPathNotFound(target_path, rroot)

    # 6.5 fill baseline/meta.json target_path_sha256 NOW, before step 7 may
    # backup scenario_dir (when target_path self-references it, the backup
    # would otherwise move the tree away and leave us hashing an empty
    # directory → sha256("") = e3b0c44... silently committed).
    # _target_path_sha256 raises EmptyTargetPath / TargetPathNotFound on
    # the broken configs that used to pass through silently.
    target_sha = _target_path_sha256(rroot, target_path)
    meta_path = staging / "baseline" / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["target_path_sha256"] = target_sha
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 7. ScenarioDirConflict guard + optional backup
    scenario_dir = rroot / "skills" / session.skill_name / "evals" / session.scenario_name
    backup_path: Path | None = None
    if scenario_dir.exists() and any(scenario_dir.iterdir()):
        if not overwrite:
            raise ScenarioDirConflict(scenario_dir)
        backup_path = _backup_existing(scenario_dir)
    elif scenario_dir.exists():
        # empty dir — remove so move can land
        scenario_dir.rmdir()

    # 8. compute kept dim set (default: keep all if user said nothing)
    if feedback["keep_dimensions"]:
        kept = list(feedback["keep_dimensions"])
    else:
        kept = list(draft.items.keys())
    dropped = set(feedback["drop_dimensions"])
    kept = [i for i in kept if i not in dropped]

    # 10. extract "这次录制为什么算成功" section from draft so judge_prompt
    # gets a non-empty rationale block.
    success_rationale = _extract_success_rationale(draft.raw)

    # 11. build judge_prompt.md
    judge_md = _build_judge_prompt(
        session=session, draft=draft, kept_ids=kept,
        threshold_overrides=feedback["threshold_overrides"],
        new_negative_cases=feedback["new_negative_cases"],
        success_rationale=success_rationale,
    )
    (staging / "judge_prompt.md").write_text(judge_md, encoding="utf-8")

    # 12. P3 double-insurance assertions
    tool_names = _collect_tool_names_from_mock_rounds(staging / "mock_rounds")
    assertions = _build_p3_double_insurance_assertions(tool_names)
    _validate_assertions_list(assertions)

    # 13. write assertions/recorded.yaml (companion human-readable copy)
    assertions_dir = staging / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    (assertions_dir / "recorded.yaml").write_text(
        yaml.safe_dump(
            assertions, sort_keys=False, allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )

    # 14. build + validate scenario.yaml
    threshold = float(
        feedback["threshold_overrides"].get(
            "pass_threshold", draft.pass_threshold,
        )
    )
    scenario_yaml = _build_scenario_yaml(
        query=query, target_path=target_path,
        threshold=threshold, assertions=assertions,
        rubric=judge_md,
    )
    _validate_scenario_yaml(scenario_yaml, scenario_dir)
    (staging / "scenario.yaml").write_text(
        yaml.safe_dump(
            scenario_yaml, sort_keys=False, allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )

    # 15. clean per-session bookkeeping files we don't want in target
    for cleanup in ("judge_candidates_draft.md", "llm_error.txt"):
        p = staging / cleanup
        if p.exists():
            p.unlink()

    # 15.5 snapshot staging for the recording report BEFORE the atomic
    # move — commit_finalize deletes judge_candidates_draft.md / llm_error
    # at step 15 and warnings.txt at step 17, so reconstructing post-move
    # would lose those fields. Failures here are swallowed; the report is
    # a nice-to-have, not load-bearing.
    _staging_snapshot = None
    try:
        from one_context.recorder import report as _report
        _staging_snapshot = _report.collect_from_staging(session)
    except Exception:
        _staging_snapshot = None

    # 16. move staging → target (atomic with cross-fs fallback)
    try:
        _move_staging_to_target(staging, scenario_dir)
    except OSError as e:
        # Restore backup if we made one and the move failed.
        if backup_path is not None and backup_path.exists() and not scenario_dir.exists():
            shutil.move(str(backup_path), str(scenario_dir))
        raise CommitFailure(
            "move_failure",
            f"could not move staging to {scenario_dir}: {e}",
        ) from e

    # 17. round up warnings.txt content from inside the moved tree
    warnings: list[str] = []
    warnings_file = scenario_dir / "warnings.txt"
    if warnings_file.is_file():
        warnings = [
            line for line in warnings_file.read_text(
                encoding="utf-8"
            ).splitlines() if line.strip()
        ]
        warnings_file.unlink()  # not part of the scenario contract

    # 18. session bookkeeping: status → committed, clear active.json,
    # rmtree staging only (keep session.json for post-commit audit / load_session).
    session.status = "committed"
    save_session(session)
    af = _active_file()
    if af.exists():
        try:
            data = json.loads(af.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        if isinstance(data, dict) and data.get("session_id") == session_id:
            af.unlink()
    shutil.rmtree(staging, ignore_errors=True)

    result = {
        "scenario_dir": str(scenario_dir),
        "files_written": _list_files_recursive(scenario_dir),
        "warnings": warnings,
        "scenario_yaml_path": str(scenario_dir / "scenario.yaml"),
        "backup_path": str(backup_path) if backup_path else None,
    }

    # 19. recording report (committed view) — best-effort.
    try:
        from one_context.recorder import report as _report
        report_path = _report.render_committed(
            scenario_dir=scenario_dir,
            staging_snapshot=_staging_snapshot,
            commit_result=result,
        )
        if report_path is not None:
            rel = str(report_path.relative_to(scenario_dir))
            if rel not in result["files_written"]:
                result["files_written"] = sorted(result["files_written"] + [rel])
    except Exception:
        pass

    return result


_SUCCESS_RATIONALE_RE = re.compile(
    r"##\s*这次录制为什么算成功\s*\n+(.*?)(?=\n##\s|\Z)",
    re.DOTALL,
)


def _extract_success_rationale(draft_md: str) -> str:
    m = _SUCCESS_RATIONALE_RE.search(draft_md)
    if not m:
        return ""
    return m.group(1).strip()


__all__ = [
    "CommitFailure",
    "InvalidFinalizeFeedback",
    "TargetPathNotFound",
    "EmptyTargetPath",
    "ScenarioDirConflict",
    "commit_finalize_session",
]
