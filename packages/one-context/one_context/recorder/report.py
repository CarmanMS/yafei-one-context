"""Recording-report renderer.

Produces an HTML dashboard that surfaces the recorder's three-step output
(start_recording → finalize → commit_finalize). It is **independent** of
the eval `report.html` — recording cares about candidate-draft review and
diagnostics, not score / diff / trace.

Two entry points:

- `render_staging(session)` — called at the end of `finalize_session`;
  writes `<session_dir>/staging/recording_report.html`. Idempotent
  (overwrites on each finalize re-run).
- `render_committed(scenario_dir, staging_snapshot, commit_result)` —
  called at the end of a successful `commit_finalize`; writes
  `<scenario_dir>/_recording/recording_report.html`. The caller must
  capture a staging snapshot BEFORE the atomic `shutil.move`, because
  staging is gone by the time we render.

Failure-mode policy: every public function swallows its own errors and
returns the output path (or None). Recording-report failures must not
break the recorder's main flow.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from one_context.recorder.session import Session

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
    lstrip_blocks=False,
)

# Mirror MockRound's hard cap; show a "download" link beyond this.
_ROUND_PREVIEW_LIMIT = 64 * 1024


# ──────────────────────────────────────────────────────────────────────
# format helpers
# ──────────────────────────────────────────────────────────────────────


def _fmt_size(n: Optional[int]) -> str:
    if n is None:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_json_optional(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _collect_files_under(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        try:
            body = p.read_text(encoding="utf-8")
            is_binary = False
        except OSError:
            continue
        except UnicodeDecodeError:
            body = f"<binary, {size} B>"
            is_binary = True
        out.append({
            "path": str(p.relative_to(root)),
            "size": size,
            "size_human": _fmt_size(size),
            "body": body,
            "is_binary": is_binary,
        })
    return out


# ──────────────────────────────────────────────────────────────────────
# data collection
# ──────────────────────────────────────────────────────────────────────


@dataclass
class StagingSnapshot:
    """Frozen view of staging/ captured before commit_finalize moves it.

    `render_committed` operates from this so it does not depend on whether
    the source tree still exists at render time.
    """

    skill_name: str
    scenario_name: str
    session_id: str
    cc_session_id: Optional[str]
    started_at: str
    status: str
    draft_md: str
    draft_present: bool
    draft_degraded: bool
    rounds: list[dict[str, Any]]
    baseline_artifacts: list[dict[str, Any]]
    baseline_final_text: str
    baseline_meta: dict[str, Any]
    warnings: list[str]
    llm_error: str
    last_commit_outcome: Optional[dict[str, Any]]
    # Live-mode extras
    live_rounds: list[dict[str, Any]] = None  # type: ignore[assignment]
    live_status: dict[str, Any] = None  # type: ignore[assignment]
    is_live: bool = False


_DEGRADED_MARKER = "LLM 起草失败"


def _collect_rounds(mock_rounds_dir: Path) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = []
    if not mock_rounds_dir.is_dir():
        return rounds
    for f in sorted(mock_rounds_dir.glob("*.yaml")):
        try:
            raw = f.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError:
            data = {}
        size = len(raw.encode("utf-8"))
        truncated = size > _ROUND_PREVIEW_LIMIT
        preview = raw if not truncated else raw[: _ROUND_PREVIEW_LIMIT] + "\n# ... truncated"
        tool_input = data.get("tool_input") or {}
        try:
            args_summary = json.dumps(tool_input, ensure_ascii=False)[:200]
        except (TypeError, ValueError):
            args_summary = repr(tool_input)[:200]
        rounds.append({
            "round_id": data.get("round_id") or f.stem,
            "tool_name": data.get("tool_name") or "?",
            "boundary_type": data.get("boundary_type") or "?",
            "args_summary": args_summary,
            "size": size,
            "size_human": _fmt_size(size),
            "truncated": truncated,
            "preview": preview,
            "file_name": f.name,
        })
    return rounds


def collect_from_staging(session: Session) -> StagingSnapshot:
    """Read everything `render_staging` needs from a recording-stage staging dir."""
    session_dir = Path(session.recording_dir)
    staging = session_dir / "staging"

    draft_path = staging / "judge_candidates_draft.md"
    draft_md = _read_optional(draft_path)
    draft_present = draft_path.is_file()
    draft_degraded = _DEGRADED_MARKER in draft_md

    warnings_text = _read_optional(staging / "warnings.txt")
    warnings = [
        line for line in warnings_text.splitlines() if line.strip()
    ]

    return StagingSnapshot(
        skill_name=session.skill_name,
        scenario_name=session.scenario_name,
        session_id=session.session_id,
        cc_session_id=session.cc_session_id,
        started_at=session.started_at,
        status=session.status,
        draft_md=draft_md,
        draft_present=draft_present,
        draft_degraded=draft_degraded,
        rounds=_collect_rounds(staging / "mock_rounds"),
        baseline_artifacts=_collect_files_under(staging / "baseline" / "artifacts"),
        baseline_final_text=_read_optional(staging / "baseline" / "final_text.md"),
        baseline_meta=_read_json_optional(staging / "baseline" / "meta.json") or {},
        warnings=warnings,
        llm_error=_read_optional(staging / "llm_error.txt"),
        last_commit_outcome=_read_json_optional(staging / "last_commit_outcome.json"),
        live_rounds=[],
        live_status={},
        is_live=False,
    )


def collect_from_committed(scenario_dir: Path) -> Optional[StagingSnapshot]:
    """Reconstruct a snapshot from a finalized scenario_dir (post-move).

    Used as a fallback when `render_committed` is called without the
    pre-move snapshot; not all fields survive (draft_md is gone — it was
    intentionally deleted in commit_finalize step 15).
    """
    if not scenario_dir.is_dir():
        return None
    return StagingSnapshot(
        skill_name=scenario_dir.parent.parent.name,
        scenario_name=scenario_dir.name,
        session_id="",
        cc_session_id=None,
        started_at="",
        status="committed",
        draft_md="",
        draft_present=False,
        draft_degraded=False,
        rounds=_collect_rounds(scenario_dir / "mock_rounds"),
        baseline_artifacts=_collect_files_under(scenario_dir / "baseline" / "artifacts"),
        baseline_final_text=_read_optional(scenario_dir / "baseline" / "final_text.md"),
        baseline_meta=_read_json_optional(scenario_dir / "baseline" / "meta.json") or {},
        warnings=[],
        llm_error="",
        last_commit_outcome=None,
        live_rounds=[],
        live_status={},
        is_live=False,
    )


# ──────────────────────────────────────────────────────────────────────
# Live mode: rounds.jsonl streaming + status (daemon endpoints use these)
# ──────────────────────────────────────────────────────────────────────


def _truncate(s: str, n: int = 200) -> str:
    if len(s) <= n:
        return s
    return s[: n] + "…"


def _summarize_args(tool_input: Any) -> str:
    if isinstance(tool_input, dict):
        # Highlight common keys
        if "command" in tool_input:
            return _truncate(str(tool_input["command"]))
        if "url" in tool_input:
            return _truncate(str(tool_input["url"]))
        if "query" in tool_input:
            return _truncate(str(tool_input["query"]))
        if "file_path" in tool_input:
            return _truncate(str(tool_input["file_path"]))
        try:
            return _truncate(json.dumps(tool_input, ensure_ascii=False))
        except (TypeError, ValueError):
            return _truncate(repr(tool_input))
    return _truncate(str(tool_input))


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read rounds.jsonl, tolerating a half-written trailing line."""
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # tail race: hook is mid-append; skip.
            continue
    return out


def collect_live_rounds(session: Session) -> list[dict[str, Any]]:
    """Parse rounds.jsonl into the shape the Live tab expects.

    Each round dict contains: seq, round_id, tool_name, boundary_type,
    args_summary, is_failure. No timestamps — hook does not write them;
    the daemon's status endpoint derives "last activity" from file mtime.
    """
    jsonl = Path(session.recording_dir) / "rounds.jsonl"
    records = _parse_jsonl(jsonl)
    parent = session.parent_cc_session_id
    target = session.cc_session_id  # may be None until M8 backfill

    out: list[dict[str, Any]] = []
    seq = 0
    for r in records:
        sid = r.get("cc_session_id")
        if parent and sid == parent:
            # parent cc's own noise; finalize filters these out, mirror here
            continue
        if target and sid and sid != target:
            continue
        seq += 1
        tool_name = r.get("tool_name", "?")
        out.append({
            "seq": seq,
            "round_id": r.get("round_id") or f"round-{seq}",
            "tool_name": tool_name,
            "boundary_type": r.get("boundary_type") or "?",
            "args_summary": _summarize_args(r.get("tool_input")),
            "is_failure": bool(r.get("_failure")),
            "event_type": r.get("event_type") or "",
        })
    return out


def collect_live_status(session: Session) -> dict[str, Any]:
    """Heartbeat data — drives the Live tab's status bar."""
    session_dir = Path(session.recording_dir)
    jsonl = session_dir / "rounds.jsonl"
    staging = session_dir / "staging"
    last_mtime = 0.0
    if jsonl.is_file():
        try:
            last_mtime = jsonl.stat().st_mtime
        except OSError:
            last_mtime = 0.0
    rounds = collect_live_rounds(session)
    now = time.time()
    last_activity_seconds = (
        (now - last_mtime) if last_mtime > 0 else None
    )
    current_tool = rounds[-1]["tool_name"] if rounds else None
    return {
        "session_id": session.session_id,
        "skill": session.skill_name,
        "scenario": session.scenario_name,
        "status": session.status,
        "round_count": len(rounds),
        "last_activity_seconds": last_activity_seconds,
        "current_tool": current_tool,
        "finalize_present": (staging / "judge_candidates_draft.md").is_file(),
        "commit_present": session.status == "committed",
        "now": _iso_utc_now(),
    }


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_from_live(session: Session) -> StagingSnapshot:
    """Live-mode snapshot: union of staging (if any) + live rounds + status.

    Falls back to mostly-empty fields when staging does not yet exist
    (during pure recording phase).
    """
    base = collect_from_staging(session)
    base.live_rounds = collect_live_rounds(session)
    base.live_status = collect_live_status(session)
    base.is_live = True
    return base


def render_live_html(session: Session) -> str:
    """Render the report template against a live snapshot. Returns html.

    Daemon's `GET /report.html` calls this on every request.
    """
    snap = collect_from_live(session)
    mode = "live" if session.status in ("recording", "finalizing") else "committed"
    view = _build_view(snap, mode=mode, commit_result=None)
    tmpl = _ENV.get_template("recording_report.html.j2")
    return tmpl.render(**view)


# ──────────────────────────────────────────────────────────────────────
# Draft parsing → keep/drop checkbox seeds
# ──────────────────────────────────────────────────────────────────────

import re

_HEADING_RE = re.compile(r"^###\s+([DF]\d+):\s*(.*?)\s*$", re.MULTILINE)


def _parse_draft_dimensions(draft_md: str) -> list[dict[str, str]]:
    """Cheap regex-only parse — returns [{id, name}] for D/F headings.

    Mirrors commit_finalize._parse_candidate_draft's headings extraction
    so the checkbox set matches what the LLM feedback parser will accept.
    """
    out: list[dict[str, str]] = []
    for m in _HEADING_RE.finditer(draft_md or ""):
        out.append({"id": m.group(1), "name": m.group(2).strip()})
    return out


# ──────────────────────────────────────────────────────────────────────
# view dict
# ──────────────────────────────────────────────────────────────────────


def _build_view(snap: StagingSnapshot, mode: str, commit_result: Optional[dict[str, Any]]) -> dict[str, Any]:
    dims = _parse_draft_dimensions(snap.draft_md)
    # When `is_live` the report polls /api/* every 1.5s; when not live
    # (staging/committed snapshots written to disk), the Live tab shows
    # the frozen rounds as a historical trace replay.
    live_rounds = snap.live_rounds or []
    if not live_rounds and snap.rounds:
        # Static-render fallback: reconstruct Live-shape rows from the
        # finalized mock_rounds so historical replay still works.
        live_rounds = [
            {
                "seq": i + 1,
                "round_id": r["round_id"],
                "tool_name": r["tool_name"],
                "boundary_type": r["boundary_type"],
                "args_summary": r["args_summary"],
                "is_failure": False,
                "event_type": "",
            }
            for i, r in enumerate(snap.rounds)
        ]
    overview = {
        "skill": snap.skill_name,
        "scenario": snap.scenario_name,
        "session_id": snap.session_id,
        "cc_session_id": snap.cc_session_id or "(unresolved)",
        "started_at": snap.started_at,
        "status": snap.status,
        "round_count": len(snap.rounds) if snap.rounds else len(live_rounds),
        "warnings_count": len(snap.warnings),
        "artifact_count": len(snap.baseline_artifacts),
        "draft_degraded": snap.draft_degraded,
        "draft_present": snap.draft_present,
        "has_llm_error": bool(snap.llm_error.strip()),
        "last_commit_outcome": snap.last_commit_outcome,
        "mode": mode,
    }
    # Tab visibility — keep tab list stable across lifecycle, just gray.
    is_recording = snap.status == "recording"
    has_staging = snap.draft_present or bool(snap.rounds) or bool(snap.baseline_artifacts)
    tab_state = {
        "live_enabled": True,            # always available; just empty in pure-committed
        "draft_enabled": has_staging and snap.draft_present,
        "rounds_enabled": bool(snap.rounds),
        "baseline_enabled": bool(snap.baseline_artifacts) or bool(snap.baseline_final_text),
        "diagnostics_enabled": True,
    }
    return {
        "overview": overview,
        "mode": mode,
        "is_live": snap.is_live,
        "is_recording": is_recording,
        "draft_md": snap.draft_md,
        "draft_dimensions": dims,
        "rounds": snap.rounds,
        "live_rounds": live_rounds,
        "live_status": snap.live_status or {},
        "tab_state": tab_state,
        "baseline_artifacts": snap.baseline_artifacts,
        "baseline_final_text": snap.baseline_final_text,
        "baseline_meta": snap.baseline_meta,
        "warnings": snap.warnings,
        "llm_error": snap.llm_error,
        "last_commit_outcome": snap.last_commit_outcome,
        "commit_result": commit_result or {},
    }


# ──────────────────────────────────────────────────────────────────────
# public API
# ──────────────────────────────────────────────────────────────────────


def render_staging(session: Session) -> Optional[Path]:
    """Render the staging-phase report. Never raises — returns None on failure."""
    try:
        snap = collect_from_staging(session)
        view = _build_view(snap, mode="staging", commit_result=None)
        tmpl = _ENV.get_template("recording_report.html.j2")
        out = Path(session.recording_dir) / "staging" / "recording_report.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tmpl.render(**view), encoding="utf-8")
        return out
    except Exception:
        return None


def render_committed(
    scenario_dir: Path,
    staging_snapshot: Optional[StagingSnapshot] = None,
    commit_result: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    """Render the committed-phase report. Never raises — returns None on failure.

    `staging_snapshot` should be captured BEFORE the atomic move so we
    preserve draft_md / warnings / llm_error (commit_finalize deletes
    those during step 15-17). If None, we degrade to reading the moved
    scenario_dir directly (no draft).
    """
    try:
        scenario_dir = Path(scenario_dir)
        snap = staging_snapshot or collect_from_committed(scenario_dir)
        if snap is None:
            return None
        view = _build_view(snap, mode="committed", commit_result=commit_result)
        tmpl = _ENV.get_template("recording_report.html.j2")
        out = scenario_dir / "_recording" / "recording_report.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tmpl.render(**view), encoding="utf-8")
        return out
    except Exception:
        return None
