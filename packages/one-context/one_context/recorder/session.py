"""Recording session state machine + on-disk layout (Phase 2.8 M1).

Layout under `ONECXT_RECORDER_ROOT` (default `/tmp/onecxt-recorder/`):

    <root>/
    ├── active.json                 # single-session lock; absent = no active
    └── <session_id>/
        ├── session.json            # full Session metadata + status
        ├── rounds.jsonl            # hook append target (M2 writes; M1 placeholder)
        └── workspace/              # baseline snapshot staging (M3 fills; M1 placeholder)

State machine (M1 only implements `recording` and `aborted`; the rest are
the contract for later milestones):

    recording → finalizing → committed
              ↘             ↗
                  aborted

`active.json` is the single-session lock: `start_session` refuses to
create a new session while another sits in `active.json`. `abort_session`
clears it; `commit_finalize` (M4) also clears it.

External-tool classification (`is_external_tool`) is the M2 hook filter
source-of-truth (design §6.5): tools recorded into `mock_rounds/` are
those that touch the world (network / shell / MCP bridges); local cc
tools (Read / Write / Edit / Grep / ...) are re-run live during replay.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

SessionStatus = Literal["recording", "finalizing", "committed", "aborted"]

# External tools the recorder mocks. cc-native tools that escape the
# sandbox (network/shell) plus everything bridged through an MCP server.
_EXTERNAL_NATIVE_TOOLS = frozenset({"WebFetch", "WebSearch", "Bash"})


class RecorderError(Exception):
    """Base class for recorder errors surfaced through MCP tool replies."""


class SessionAlreadyActive(RecorderError):
    def __init__(self, active_session_id: str) -> None:
        self.active_session_id = active_session_id
        super().__init__(
            f"recording session {active_session_id!r} is already active; "
            "finalize or abort it before starting a new one"
        )


class SessionNotFound(RecorderError):
    pass


class SessionWrongState(RecorderError):
    pass


class SkillNotFound(RecorderError):
    pass


@dataclass
class Session:
    session_id: str
    skill_name: str
    scenario_name: str
    cc_session_id: Optional[str]
    started_at: str
    status: SessionStatus
    recording_dir: str  # absolute path string
    # M8: id of the cc session that opened start_recording (the *parent*).
    # Hook filters rounds whose payload.session_id == this so the parent's
    # own tool noise does not pollute the child's recording. None when the
    # MCP server could not resolve a parent (e.g. CLAUDE_CODE_SESSION_ID
    # env not injected) — in that case the hook falls back to "first round
    # wins" cc_session_id backfill, accepting the edge risk that the
    # first round may be parent noise.
    parent_cc_session_id: Optional[str] = None

    @property
    def dir(self) -> Path:
        return Path(self.recording_dir)

    def to_dict(self) -> dict:
        return asdict(self)


# ── path helpers (resolved fresh per call so tests can monkeypatch env) ──


def recorder_root() -> Path:
    """Resolve recorder tmp root from `ONECXT_RECORDER_ROOT` env or default."""
    return Path(os.environ.get("ONECXT_RECORDER_ROOT", "/tmp/onecxt-recorder"))


def resolve_repo_root(explicit: Optional[Path] = None) -> Path:
    """Project root for git status / target_path hashing.

    Precedence: explicit arg → `ONECXT_RECORDER_REPO_ROOT` env → `Path.cwd()`.
    Shared by finalize (meta.working_tree_sha) and commit_finalize
    (target_path_sha256 + abs_target existence check) so both stages hash
    against the same root.
    """
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("ONECXT_RECORDER_REPO_ROOT")
    if env:
        return Path(env)
    return Path.cwd()


def _active_file() -> Path:
    return recorder_root() / "active.json"


def _session_dir(session_id: str) -> Path:
    return recorder_root() / session_id


def _ensure_root() -> None:
    recorder_root().mkdir(parents=True, exist_ok=True)


# ── active.json single-session lock ──────────────────────────────────────


def _read_active() -> Optional[dict]:
    f = _active_file()
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    # treat empty/null as no active session
    if not data:
        return None
    return data


def _write_active(payload: dict) -> None:
    _ensure_root()
    _active_file().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _clear_active() -> None:
    f = _active_file()
    if f.exists():
        f.unlink()


def get_active_session_id() -> Optional[str]:
    data = _read_active()
    return None if data is None else data.get("session_id")


# ── session IO ───────────────────────────────────────────────────────────


def load_session(session_id: str) -> Session:
    session_file = _session_dir(session_id) / "session.json"
    if not session_file.exists():
        raise SessionNotFound(
            f"session {session_id!r} not found at {session_file}"
        )
    data = json.loads(session_file.read_text(encoding="utf-8"))
    # Forward-compat: ignore unknown keys in session.json (e.g. fields
    # added by a future recorder version) and supply defaults for fields
    # that exist on the dataclass but were missing on disk (e.g. M1-era
    # session.json that predates M8's `parent_cc_session_id`).
    known = {f.name for f in dataclasses.fields(Session)}
    return Session(**{k: v for k, v in data.items() if k in known})


def save_session(session: Session) -> None:
    session_file = session.dir / "session.json"
    session_file.write_text(
        json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── start / abort (M1) ───────────────────────────────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Stale lock recovery thresholds (Phase 2.8 M5 — auto-recovery).
# Reasoning: a real recording session writes to its cc transcript
# constantly (every tool call); 10 minutes of no transcript activity
# almost certainly means cc died (window closed, Ctrl-C, crash). The
# 6h started_at ceiling is a backstop for the rare case where the
# transcript path itself can't be resolved (e.g. cc_session_id absent
# from active.json) — no real recording lasts that long.
_STALE_TRANSCRIPT_SECONDS = 10 * 60
_STALE_STARTED_AT_SECONDS = 6 * 60 * 60
# Old session UUID dirs older than this get rmtree'd on start (M3).
_OLD_SESSION_DIR_DAYS = 30


def _find_cc_transcript_for_session(cc_session_id: Optional[str]) -> Optional[Path]:
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


def _is_active_session_stale(active: dict) -> tuple[bool, str]:
    """Return (is_stale, reason) for an active.json payload.

    Stale when ANY of:
      a) cc_session_id transcript mtime older than _STALE_TRANSCRIPT_SECONDS
      b) cc_session_id set but transcript file not found AND
         started_at older than _STALE_TRANSCRIPT_SECONDS
         (cc died before writing, or transcript was deleted)
      c) started_at older than _STALE_STARTED_AT_SECONDS (hard backstop)
    """
    import time as _time

    cc_sid = active.get("cc_session_id")
    started_at = active.get("started_at")
    started_age: Optional[float] = None
    if started_at:
        try:
            started_age = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(started_at)
            ).total_seconds()
        except (ValueError, TypeError):
            started_age = None

    if cc_sid:
        transcript = _find_cc_transcript_for_session(cc_sid)
        if transcript is not None:
            try:
                mtime_age = _time.time() - transcript.stat().st_mtime
            except OSError:
                mtime_age = None
            if mtime_age is not None and mtime_age > _STALE_TRANSCRIPT_SECONDS:
                return True, (
                    f"cc transcript {transcript.name} not updated for "
                    f"{int(mtime_age // 60)}m {int(mtime_age % 60)}s"
                )
            if mtime_age is not None:
                # transcript fresh → still recording, not stale
                return False, ""
        else:
            # transcript not found
            if started_age is not None and started_age > _STALE_TRANSCRIPT_SECONDS:
                return True, (
                    f"cc transcript for {cc_sid[:8]}... not found "
                    f"and session started {int(started_age // 60)}m ago"
                )

    if started_age is not None and started_age > _STALE_STARTED_AT_SECONDS:
        return True, (
            f"recording session started {int(started_age // 3600)}h ago, "
            f"exceeds {_STALE_STARTED_AT_SECONDS // 3600}h hard ceiling"
        )
    return False, ""


def _try_recover_stale_active() -> tuple[bool, str]:
    """If active.json points at a stale session, auto-abort it.

    Returns (recovered, reason). recovered=True means active.json is now
    gone (next start_session can proceed). reason carries a human-readable
    note suitable for logging or surfacing in the SessionAlreadyActive
    error when recovery did NOT happen.
    """
    active = _read_active()
    if active is None:
        return False, ""

    sid = active.get("session_id")
    if not sid:
        # malformed/empty active.json — just clear it
        _clear_active()
        return True, "cleared malformed active.json (no session_id)"

    # Orphan check: active.json refers to a session whose session.json
    # is gone (e.g. /tmp got cleaned). Nothing to abort — just unlock.
    sess_file = _session_dir(sid) / "session.json"
    if not sess_file.exists():
        _clear_active()
        return True, f"cleared orphan active.json (session dir gone): {sid}"

    stale, reason = _is_active_session_stale(active)
    if not stale:
        return False, reason

    try:
        abort_session(sid, keep_staging=True)
        return True, f"auto-aborted stale session {sid[:8]}...: {reason}"
    except Exception as e:
        # Last resort: clear lock so user is not permanently stuck.
        _clear_active()
        return True, (
            f"abort_session failed ({type(e).__name__}); cleared lock "
            f"anyway: {reason}"
        )


def _purge_old_session_dirs(*, days: int = _OLD_SESSION_DIR_DAYS) -> int:
    """Remove session UUID dirs older than `days`. Returns count removed.

    Skips the currently-active session and anything that fails to stat.
    Bounded by `days` so a sweep can't accidentally nuke a live session.
    """
    import time as _time

    root = recorder_root()
    if not root.is_dir():
        return 0
    cutoff = _time.time() - days * 86400
    active = _read_active() or {}
    active_sid = active.get("session_id")
    removed = 0
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if entry.name == active_sid:
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
    except OSError:
        return removed
    return removed


def start_session(
    skill_name: str,
    scenario_name: str,
    cc_session_id: Optional[str] = None,
    *,
    repo_root: Optional[Path] = None,
    parent_cc_session_id: Optional[str] = None,
    force: bool = False,
) -> Session:
    """Open a new recording session.

    When `repo_root` is given, `skills/<skill_name>/SKILL.md` must exist
    under it. Tests pass `repo_root=None` to skip that check.

    `parent_cc_session_id` (M8): id of the cc session that called
    `start_recording` — typically the *parent* cc that drives the
    recorder skill. The hook uses it to filter the parent's own tool
    noise from the recording. Defaults to None when unknown.

    Phase 2.8 M5 — lock auto-recovery + force:
    - First pass: opportunistic stale-lock recovery (cc transcript idle
      >10m, orphan session dir, started_at >6h) auto-aborts the old
      session and frees the lock. Removes the common "I closed the
      window, now I can't start a new recording" papercut without
      risking live-session interruption.
    - `force=True` skips the stale check and forcibly aborts whatever
      sits in active.json. Use when you know the previous session is
      dead but the stale heuristics haven't tripped yet (e.g. window
      closed seconds ago, transcript mtime still recent). The aborted
      session's staging is kept so you can inspect what was recorded
      before the force.
    - Fresh active session (no stale signal, no force) → still raises
      SessionAlreadyActive.

    Also opportunistically rmtree's session dirs older than 30 days so
    /tmp doesn't accumulate UUIDs over time.
    """
    if not skill_name or not skill_name.strip():
        raise ValueError("skill_name must not be empty")
    if not scenario_name or not scenario_name.strip():
        raise ValueError("scenario_name must not be empty")

    _ensure_root()
    _purge_old_session_dirs()

    if force:
        # Skip stale check; nuke whatever lock exists.
        active = _read_active()
        if active is not None:
            sid = active.get("session_id")
            if sid and (_session_dir(sid) / "session.json").exists():
                try:
                    abort_session(sid, keep_staging=True)
                except Exception:
                    _clear_active()
            else:
                _clear_active()
    else:
        _try_recover_stale_active()

    active = _read_active()
    if active is not None:
        raise SessionAlreadyActive(active.get("session_id", "<unknown>"))

    if repo_root is not None:
        skill_md = Path(repo_root) / "skills" / skill_name / "SKILL.md"
        if not skill_md.exists():
            raise SkillNotFound(
                f"skill {skill_name!r}: SKILL.md not found at {skill_md}"
            )

    session_id = str(uuid.uuid4())
    sdir = _session_dir(session_id)
    sdir.mkdir(parents=True, exist_ok=False)
    (sdir / "rounds.jsonl").touch()  # M2 appends; placeholder for M1
    (sdir / "workspace").mkdir()      # M3 fills; placeholder for M1

    now = _utc_now_iso()
    session = Session(
        session_id=session_id,
        skill_name=skill_name,
        scenario_name=scenario_name,
        cc_session_id=cc_session_id,
        started_at=now,
        status="recording",
        recording_dir=str(sdir),
        parent_cc_session_id=parent_cc_session_id,
    )
    save_session(session)
    _write_active(
        {
            "session_id": session_id,
            "skill_name": skill_name,
            "scenario_name": scenario_name,
            "cc_session_id": cc_session_id,
            "parent_cc_session_id": parent_cc_session_id,
            "started_at": now,
        }
    )
    return session


def record_cc_session_id(session_id: str, cc_session_id: str) -> None:
    """Backfill the child cc_session_id once the hook observes it (M8).

    Idempotent: only writes when the current session.cc_session_id is
    falsy. Updates both session.json and active.json so finalize sees
    the resolved id without a second on-disk patch.
    """
    if not cc_session_id:
        return
    try:
        session = load_session(session_id)
    except SessionNotFound:
        return
    if session.cc_session_id:
        return
    session.cc_session_id = cc_session_id
    save_session(session)
    # Mirror into active.json so monitoring tools (and a crash-recovery
    # path that reads active.json without loading session.json) agree.
    active = _read_active()
    if active and active.get("session_id") == session_id:
        active["cc_session_id"] = cc_session_id
        _write_active(active)


def abort_session(
    session_id: str, *, keep_staging: bool = False
) -> dict:
    """Mark session aborted; remove on-disk staging unless `keep_staging`.

    Always clears `active.json` if it points at this session_id. Safe to
    call on a session in any non-`committed` state.
    """
    session = load_session(session_id)
    session.status = "aborted"
    # Persist state to session.json BEFORE rmtree so a kept session has a
    # truthful status; the dir vanishes afterwards anyway when not kept.
    save_session(session)

    kept_paths: list[str] = []
    if keep_staging:
        kept_paths = [str(session.dir)]
    else:
        shutil.rmtree(session.dir, ignore_errors=True)

    if get_active_session_id() == session_id:
        _clear_active()

    return {"aborted_at": _utc_now_iso(), "kept_paths": kept_paths}


# ── tool boundary classification (M2 hook filter source) ─────────────────


def is_external_tool(tool_name: str) -> bool:
    """True when the tool should be recorded into mock_rounds/.

    Anything bridged through MCP (`mcp__*`) or one of the cc-native
    network/shell tools (WebFetch/WebSearch/Bash) is "external"; local
    tools (Read/Write/Edit/Grep/Glob/TodoWrite/...) are re-run live
    during replay and are NOT mocked.
    """
    if not tool_name:
        return False
    if tool_name.startswith("mcp__"):
        return True
    return tool_name in _EXTERNAL_NATIVE_TOOLS
