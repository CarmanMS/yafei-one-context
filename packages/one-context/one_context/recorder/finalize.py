"""finalize_session — recorder Stage A (Phase 2.8 M3).

Turns a `recording` session's append-only `rounds.jsonl` + workspace
snapshot into staged artifacts under `<session_dir>/staging/`:

    staging/
    ├── mock_rounds/round-NN-<slug>-<hash8>.yaml   # MockRound-compatible
    ├── baseline/
    │   ├── artifacts/...                           # recursive workspace snapshot
    │   ├── final_text.md                           # cc last assistant text (best-effort)
    │   └── meta.json                               # cc_cli_version / digests / sha
    ├── judge_candidates_draft.md                   # LLM-drafted candidate list
    └── llm_error.txt                               # only when LLM degraded

M4 `commit_finalize` is what physically moves `staging/` into
`skills/<skill>/evals/<scenario>/`; finalize itself never touches the
target. This split lets finalize be retried (status stays `finalizing`
on degraded paths) without disturbing committed scenarios.

Contracts inherited from M2 (`hook_writer.py` → jsonl):

1. **cc_session_id filter** — jsonl can contain rounds from the parent
   cc (when the recorded skill spawns subprocess cc) plus the target
   cc. We pin to `session.cc_session_id`; when absent, derive from the
   most-frequent id in the jsonl with a warning so the session still
   finalizes instead of failing on a missing field.
2. **jsonl-only field drop** — `event_type`, `cc_session_id`, `_failure`
   are jsonl-bookkeeping that `MockRound` (`extra="forbid"`) would
   reject. Stripped before `model_validate`.
3. **failed-round boundary_type rewrite** — hook writes
   `boundary_type=failed_tool` for `PostToolUseFailure`, but
   `MockRound` only allows `local_tool` / `mcp_call`. We re-derive from
   the tool name so the yaml validates; the `tool_result` is already
   in cc-native `{"error": ..., "is_error": True}` shape so replay
   reads it as "this past tool call failed".
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from one_context.eval.session_inject import (
    MAX_TOOL_RESULT_BYTES,
    MockRound,
    detect_cc_version,
)
from one_context.recorder import llm_client
from one_context.recorder.prompts import (
    load_negative_case_library,
    render_prompt,
)
from one_context.recorder.session import (
    Session,
    SessionWrongState,
    load_session,
    resolve_repo_root,
    save_session,
)

# Fields written by hook_writer but rejected by MockRound's extra="forbid".
_JSONL_ONLY_FIELDS = {"event_type", "cc_session_id", "_failure"}

# How many of cc's final assistant text bytes we pass to the LLM as
# context. The full final_text.md is also written; this is just the
# prompt-side cap to keep the draft request within a sane token budget.
_FINAL_TEXT_HEAD_BYTES = 500


# ── data shape helpers ──────────────────────────────────────────────────


def _strip_jsonl_only(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in _JSONL_ONLY_FIELDS}


def _coerce_boundary_type(tool_name: str, raw_boundary: str | None) -> str:
    """MockRound enum only knows local_tool / mcp_call.

    `failed_tool` (M2 hook_writer) must be remapped before validation.
    """
    if raw_boundary in ("local_tool", "mcp_call"):
        return raw_boundary
    return "mcp_call" if (tool_name or "").startswith("mcp__") else "local_tool"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Malformed line is hook bug; skip but don't fail finalize.
                continue
    return records


# ── cc_session_id filter (design §13 + M2 契约 3) ──────────────────────


def _resolve_target_cc_session_id(
    session: Session, records: list[dict]
) -> tuple[str | None, list[str]]:
    """Pick which cc_session_id to keep; return (id, warnings)."""
    warnings: list[str] = []
    if session.cc_session_id:
        return session.cc_session_id, warnings

    ids: list[str] = [
        r["cc_session_id"]
        for r in records
        if isinstance(r.get("cc_session_id"), str) and r["cc_session_id"]
    ]
    if not ids:
        # No id anywhere — keep all records, hard to do better.
        return None, warnings

    counter = Counter(ids)
    unique = list(counter.keys())
    if len(unique) == 1:
        return unique[0], warnings

    most_common, _ = counter.most_common(1)[0]
    warnings.append(
        f"session.cc_session_id missing; jsonl carries {len(unique)} "
        f"distinct cc_session_ids — keeping the most frequent "
        f"({most_common!r}, {counter[most_common]}/{len(ids)})"
    )
    return most_common, warnings


def _filter_by_cc_session_id(
    records: list[dict], target: str | None
) -> list[dict]:
    if target is None:
        return records
    return [
        r for r in records
        if r.get("cc_session_id") == target or r.get("cc_session_id") is None
    ]


# ── mock_rounds yaml emission ───────────────────────────────────────────


def _truncate_tool_result_if_oversized(tool_result: Any) -> Any:
    """If tool_result exceeds MAX_TOOL_RESULT_BYTES, blow up early.

    Per MockRound's own validator the per-round cap is 1MB; finalize
    surfaces the violating round id at write time rather than letting
    pydantic do it during commit_finalize so the user knows *which* yaml
    is the problem. We don't auto-truncate — the recorder should never
    silently lose data; the user must trim the fixture.
    """
    if isinstance(tool_result, str):
        size = len(tool_result.encode("utf-8"))
    else:
        try:
            size = len(json.dumps(tool_result, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError):
            size = len(repr(tool_result).encode("utf-8"))
    return tool_result, size > MAX_TOOL_RESULT_BYTES


def _build_mock_round(record: dict) -> MockRound:
    """Convert one jsonl record → validated MockRound."""
    stripped = _strip_jsonl_only(record)
    stripped["boundary_type"] = _coerce_boundary_type(
        stripped.get("tool_name", ""), stripped.get("boundary_type")
    )
    # Drop any unexpected keys defensively; MockRound forbids extras.
    allowed = {
        "round_id", "tool_name", "tool_input",
        "tool_result", "assistant_thinking", "boundary_type",
    }
    clean = {k: v for k, v in stripped.items() if k in allowed}
    return MockRound.model_validate(clean)


def _yaml_dump_round(mr: MockRound) -> str:
    return yaml.safe_dump(
        mr.model_dump(),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def _write_mock_rounds(
    rounds: list[MockRound], target_dir: Path
) -> dict[str, str]:
    """Write every MockRound to a yaml file; return digest dict."""
    target_dir.mkdir(parents=True, exist_ok=True)
    digest: dict[str, str] = {}
    for mr in rounds:
        path = target_dir / f"{mr.round_id}.yaml"
        text = _yaml_dump_round(mr)
        path.write_text(text, encoding="utf-8")
        digest[mr.round_id] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return digest


# ── baseline snapshot ───────────────────────────────────────────────────


def _snapshot_workspace(
    workspace_dir: Path, dest_dir: Path
) -> int:
    """Recursive copy workspace_dir → dest_dir; return file count."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not workspace_dir.exists() or not workspace_dir.is_dir():
        return 0
    n = 0
    for src in workspace_dir.rglob("*"):
        rel = src.relative_to(workspace_dir)
        dst = dest_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    return n


def _mirror_external_workspace(
    src_dir: Path, workspace_dir: Path
) -> tuple[int, list[str]]:
    """M9: copy an external directory into session workspace/ pre-snapshot.

    Returns (file_count, warnings). Used when the recorded child cc
    writes baseline artifacts to the project tree (e.g. `production/`)
    instead of `session_dir/workspace/` — the design assumption fails
    in practice (design §10 M3 实施新发现 + §15 R-4). Caller passes
    `workspace_mirror_from` to point us at the real source.

    Overlay semantics: existing files in `workspace_dir` are overwritten,
    extra files in `workspace_dir` are kept. No deletion. Never raises.
    """
    warnings: list[str] = []
    if not src_dir.exists():
        warnings.append(f"workspace_mirror_from not found: {src_dir}")
        return 0, warnings
    if not src_dir.is_dir():
        warnings.append(f"workspace_mirror_from is not a directory: {src_dir}")
        return 0, warnings
    workspace_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in src_dir.rglob("*"):
        rel = src.relative_to(src_dir)
        dst = workspace_dir / rel
        try:
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            elif src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                n += 1
        except OSError as e:
            warnings.append(f"mirror copy failed for {rel}: {e}")
    return n, warnings


def _ls_tree(root: Path, prefix: str = "") -> str:
    """Pretty-print a file tree (for LLM prompt context)."""
    if not root.exists():
        return "(empty)"
    lines: list[str] = []
    entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + entry.name)
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            sub = _ls_tree(entry, prefix + extension)
            if sub and sub != "(empty)":
                lines.append(sub)
    return "\n".join(lines) if lines else "(empty)"


# ── final_text.md (best-effort cc transcript lookup) ────────────────────


def _find_cc_transcript(cc_session_id: str | None) -> Path | None:
    """Locate `~/.claude/projects/*/<cc_session_id>.jsonl` by glob.

    cc stores per-project session files at
    `~/.claude/projects/<cwd-hash>/<session_id>.jsonl`. finalize doesn't
    know the cwd-hash (recorder session.json doesn't store cwd in M2),
    so we glob across all projects. Returns None when not found.
    """
    if not cc_session_id:
        return None
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.is_dir():
        return None
    try:
        for candidate in projects_root.glob(f"*/{cc_session_id}.jsonl"):
            if candidate.is_file():
                return candidate
    except OSError:
        return None
    return None


def _extract_last_assistant_text(transcript: Path) -> str:
    """Scan a cc jsonl backwards for the last assistant text block.

    cc's jsonl entries are one per line. Assistant text turns look like:
        {"type":"assistant","message":{"role":"assistant",
         "content":[{"type":"text","text":"..."}, ...]}}
    Returns empty string when nothing parseable is found.
    """
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        # cc 2.1.156 wraps the assistant turn in `message.content[]`.
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
        role = msg.get("role") or obj.get("type")
        if role != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        texts: list[str] = []
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text":
                t = blk.get("text")
                if isinstance(t, str) and t.strip():
                    texts.append(t)
        if texts:
            return "\n\n".join(texts).strip()
    return ""


def _resolve_final_text(cc_session_id: str | None) -> tuple[str, list[str]]:
    warnings: list[str] = []
    transcript = _find_cc_transcript(cc_session_id)
    if transcript is None:
        warnings.append(
            f"cc transcript for session {cc_session_id!r} not found under "
            f"~/.claude/projects; final_text.md left empty"
        )
        return "", warnings
    text = _extract_last_assistant_text(transcript)
    if not text:
        warnings.append(
            f"cc transcript {transcript} contains no parseable assistant "
            f"text turn; final_text.md left empty"
        )
    return text, warnings


def _extract_cc_model(cc_session_id: str | None) -> str:
    """Lift the first assistant turn's `message.model` from cc transcript.

    cc tags every assistant entry with the model that produced it (e.g.
    `claude-opus-4-7`). meta.json wants the cc model, NOT whatever the
    recorder LLM was using — those can differ (recorder commonly runs
    GLM/Doubao for cheap drafting while cc itself runs Claude).
    Returns empty string when transcript or assistant message is absent;
    caller falls back to env so meta.model is never None.
    """
    transcript = _find_cc_transcript(cc_session_id)
    if transcript is None:
        return ""
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        model = msg.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    return ""


def _extract_first_user_query(
    cc_session_id: str | None,
) -> str:
    """Best-effort: lift the first user-text turn from the transcript.

    Used as the `query` draft suggestion in the candidate list — design
    §10 open question #1: rather than block finalize on missing query,
    we pre-populate a candidate that the user can confirm or override
    during commit_finalize. Returns empty string on any lookup miss.
    """
    transcript = _find_cc_transcript(cc_session_id)
    if transcript is None:
        return ""
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
        role = msg.get("role") or obj.get("type")
        if role != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    t = blk.get("text")
                    if isinstance(t, str) and t.strip():
                        return t.strip()
    return ""


# ── meta.json ───────────────────────────────────────────────────────────


def _git_status_sha(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "unknown"
        return hashlib.sha256(
            (result.stdout or "").encode("utf-8")
        ).hexdigest()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unknown"


def _build_meta(
    *,
    cc_cli_version: str,
    model: str,
    cwd: Path,
    mock_rounds_digest: dict[str, str],
) -> dict:
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "cc_cli_version": cc_cli_version,
        "model": model,
        "working_tree_sha": _git_status_sha(cwd),
        # M4 commit_finalize fills target_path_sha256 once the user
        # confirms `target_path`. finalize cannot guess it.
        "target_path_sha256": None,
        "mock_rounds_digest": mock_rounds_digest,
    }


# ── LLM draft (prompt build + degrade) ──────────────────────────────────


def _rounds_summary(rounds: list[MockRound]) -> str:
    """Compact one-line-per-round summary for the LLM prompt.

    Avoids dumping full tool_result (can be 1MB); shows just enough for
    the LLM to reason about coverage.
    """
    if not rounds:
        return "(no rounds)"
    lines: list[str] = []
    for mr in rounds:
        if isinstance(mr.tool_input, dict):
            key_fields = ("url", "command", "query", "file_path", "path")
            inp = " ".join(
                f"{k}={mr.tool_input[k]!r}"
                for k in key_fields
                if k in mr.tool_input
            ) or json.dumps(mr.tool_input, ensure_ascii=False)[:120]
        else:
            inp = repr(mr.tool_input)[:120]
        if isinstance(mr.tool_result, dict) and mr.tool_result.get("is_error"):
            tail = f"FAILED: {mr.tool_result.get('error', '')[:80]}"
        elif isinstance(mr.tool_result, str):
            tail = f"{len(mr.tool_result)}B str"
        else:
            tail = f"{type(mr.tool_result).__name__}"
        lines.append(
            f"- {mr.round_id} [{mr.boundary_type}] {mr.tool_name} {inp} → {tail}"
        )
    return "\n".join(lines)


def _build_draft_prompt(
    *,
    session: Session,
    rounds: list[MockRound],
    artifacts_tree_text: str,
    final_text: str,
    query_draft: str,
) -> str:
    # repo_root lets the loader prefer the skill-owned library at
    # skills/<skill>/evals/_negative_cases.md before falling back to the
    # framework's generic _default.md template.
    from .session import resolve_repo_root

    negative_case_library = load_negative_case_library(
        session.skill_name, repo_root=resolve_repo_root()
    )
    return render_prompt(
        "finalize_judge_draft.md",
        skill_name=session.skill_name,
        scenario_name=session.scenario_name,
        rounds_summary=_rounds_summary(rounds),
        artifacts_tree=artifacts_tree_text,
        final_text_head=(final_text or "")[:_FINAL_TEXT_HEAD_BYTES] or "(empty)",
        query_draft=query_draft or "(none captured)",
        negative_case_library=negative_case_library,
    )


_DEGRADED_DRAFT = """# Judge Prompt Draft — {skill_name} / {scenario_name}

> **LLM 调用失败 · 降级 markdown**
>
> finalize 起草 LLM 调用未成功，请人工编写判定维度。错误详情见
> `<session_dir>/staging/llm_error.txt`。
>
> 当前状态：session 留在 `finalizing`，可调 `mcp__onecxt_recorder__finalize`
> 重试；也可手动改 `staging/judge_candidates_draft.md` 然后直接进
> `commit_finalize`。

## 这次录制为什么算成功

TBD（请人工补充）

## 候选 query

TBD

## 判定维度（LLM 给 0-1 分）

### D1: TBD
**判定标准**：TBD
**权重**：0.5
**covers**: []

## 虚假通过反例

### F1: TBD
**特征**：TBD
**反例数据来源**：TBD
**covers**: []

## 未覆盖反例

请人工填写。

## 总分阈值

`pass_threshold: 0.7`
"""


def _degraded_draft(session: Session) -> str:
    return _DEGRADED_DRAFT.format(
        skill_name=session.skill_name,
        scenario_name=session.scenario_name,
    )


# ── public entry ────────────────────────────────────────────────────────


def finalize_session(
    session_id: str,
    *,
    workspace_mirror_from: Optional[str | Path] = None,
    repo_root: Optional[Path] = None,
) -> str:
    """Run finalize Stage A. Return the candidate-list markdown.

    Raises `SessionWrongState` when the session is not in `recording`.
    Never raises on LLM failure — degrades to a placeholder + persists
    the raw error so the user can decide whether to retry.

    M9 `workspace_mirror_from`: an optional external directory whose
    contents are mirrored into `session_dir/workspace/` before snapshot.
    Use this when the recorded child cc wrote baseline artifacts to the
    project tree (e.g. `production/<skill>/`) instead of the recorder's
    workspace dir. The recorder originally assumed the child cc writes
    inside `session_dir/workspace/`, but in practice it writes to the
    project repo; without mirroring, baseline/artifacts/ ends up empty
    and replay loses ground truth (design §15 R-4).
    """
    session = load_session(session_id)
    if session.status != "recording":
        raise SessionWrongState(
            f"finalize_session requires status='recording', got "
            f"{session.status!r} (session_id={session_id!r})"
        )

    # Status flips to finalizing up-front so a crash mid-flight is at
    # least observable (a session stuck in `finalizing` without
    # staging/ → user knows finalize crashed and can abort cleanly).
    session.status = "finalizing"
    save_session(session)

    session_dir = session.dir
    staging = session_dir / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    mock_rounds_dir = staging / "mock_rounds"
    baseline_dir = staging / "baseline"

    # 1. read rounds.jsonl + filter by cc_session_id
    records = _read_jsonl(session_dir / "rounds.jsonl")
    target_cc, cc_warnings = _resolve_target_cc_session_id(session, records)
    records = _filter_by_cc_session_id(records, target_cc)

    # 2. build MockRound objects (drop jsonl-only fields, fix boundary_type)
    rounds: list[MockRound] = []
    for r in records:
        if not r.get("tool_name"):
            continue
        rounds.append(_build_mock_round(r))

    # 3. write yaml + digest
    digest = _write_mock_rounds(rounds, mock_rounds_dir)

    # 3.5 (M9): mirror external dir into session workspace BEFORE snapshot
    mirror_warnings: list[str] = []
    if workspace_mirror_from:
        _, mirror_warnings = _mirror_external_workspace(
            Path(workspace_mirror_from), session_dir / "workspace"
        )

    # 4. baseline artifacts snapshot (workspace/ may be empty — that's OK)
    artifacts_dir = baseline_dir / "artifacts"
    _snapshot_workspace(session_dir / "workspace", artifacts_dir)

    # 5. final_text.md (best-effort)
    final_text, final_text_warnings = _resolve_final_text(target_cc)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "final_text.md").write_text(
        final_text, encoding="utf-8"
    )

    # 6. meta.json (target_path_sha256 deferred to commit_finalize)
    rroot = resolve_repo_root(repo_root)
    cc_model = _extract_cc_model(target_cc)
    meta = _build_meta(
        cc_cli_version=detect_cc_version(),
        model=cc_model or os.environ.get(
            "ANTHROPIC_MODEL",
            os.environ.get("ONECXT_RECORDER_LLM_MODEL", "unknown"),
        ),
        cwd=rroot,
        mock_rounds_digest=digest,
    )
    (baseline_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 7. LLM-draft the candidate list (degrade on failure)
    artifacts_tree_text = _ls_tree(artifacts_dir)
    query_draft = _extract_first_user_query(target_cc)
    prompt = _build_draft_prompt(
        session=session,
        rounds=rounds,
        artifacts_tree_text=artifacts_tree_text,
        final_text=final_text,
        query_draft=query_draft,
    )

    try:
        draft_md = llm_client.call_llm_for_draft(prompt)
    except llm_client.LLMCallError as e:
        (staging / "llm_error.txt").write_text(
            f"{type(e).__name__}: {e}\n", encoding="utf-8"
        )
        draft_md = _degraded_draft(session)

    # 8. persist draft (M4 commit_finalize reads it)
    (staging / "judge_candidates_draft.md").write_text(
        draft_md, encoding="utf-8"
    )

    # Persist any warnings near the draft for transparency. Not part of
    # the schema; just an audit log for the user.
    all_warnings = cc_warnings + final_text_warnings + mirror_warnings
    if all_warnings:
        (staging / "warnings.txt").write_text(
            "\n".join(all_warnings) + "\n", encoding="utf-8"
        )

    try:
        from one_context.recorder import report as _report
        _report.render_staging(session)
    except Exception:
        pass

    return draft_md


__all__ = ["finalize_session"]
