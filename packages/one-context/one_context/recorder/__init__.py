"""one-context recording subsystem (Phase 2.8).

Captures cc-side skill executions (external tool IO + workspace
artifacts + AI-drafted judge prompts) into the
`skills/<skill>/evals/<scenario>/` fixtures consumable by `onecxt eval`
replay.

M1 (this milestone) covers the session lifecycle skeleton only:
`start_recording` + `abort` MCP tools and the on-disk session layout
under `/tmp/onecxt-recorder/`. M2 wires PostToolUse hooks; M3 finalize
turns `rounds.jsonl` into `mock_rounds/*.yaml` + baseline; M4 commits.
"""

from one_context.recorder.commit_finalize import (
    CommitFailure,
    InvalidFinalizeFeedback,
    ScenarioDirConflict,
    TargetPathNotFound,
    commit_finalize_session,
)
from one_context.recorder.finalize import finalize_session
from one_context.recorder.session import (
    RecorderError,
    Session,
    SessionAlreadyActive,
    SessionNotFound,
    SessionWrongState,
    SkillNotFound,
    abort_session,
    get_active_session_id,
    is_external_tool,
    load_session,
    recorder_root,
    save_session,
    start_session,
)

__all__ = [
    "CommitFailure",
    "InvalidFinalizeFeedback",
    "RecorderError",
    "ScenarioDirConflict",
    "Session",
    "SessionAlreadyActive",
    "SessionNotFound",
    "SessionWrongState",
    "SkillNotFound",
    "TargetPathNotFound",
    "abort_session",
    "commit_finalize_session",
    "finalize_session",
    "get_active_session_id",
    "is_external_tool",
    "load_session",
    "recorder_root",
    "save_session",
    "start_session",
]
