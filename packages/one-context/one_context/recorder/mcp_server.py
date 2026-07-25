"""Minimal MCP server for `onecxt_recorder` (Phase 2.8 M1).

Implements just enough of the MCP stdio JSON-RPC protocol for cc to
discover and invoke the two M1 tools: `start_recording` and `abort`.
`finalize` / `commit_finalize` come in M3/M4 and will register here once
their implementations land.

The handler is split from the stdio loop so unit tests can exercise the
JSON-RPC dispatch as a pure function (`handle_request`). Real cc
integration (M6) drives `main()` which reads/writes line-delimited JSON
on stdin/stdout.

Tool reply convention (MCP `tools/call` result):
- success → `{content: [{type:"text", text: <json>}], isError: false}`
- error   → `{content: [{type:"text", text: <json>}], isError: true}`
  with the JSON body carrying `{"error_kind": ..., "error": ...}` so cc
  / the recorder skill can react to known recorder errors by class name.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from one_context.recorder import commit_finalize as _commit_finalize
from one_context.recorder import finalize as _finalize
from one_context.recorder import session as _session
from one_context.recorder.commit_finalize import (
    CommitFailure,
    EmptyTargetPath,
    InvalidFinalizeFeedback,
    ScenarioDirConflict,
    TargetPathNotFound,
)
from one_context.recorder.session import (
    RecorderError,
    SessionAlreadyActive,
    SessionNotFound,
    SessionWrongState,
    SkillNotFound,
)

SERVER_NAME = "onecxt_recorder"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


# Tool registry surfaced via `tools/list`. M3/M4 will append `finalize`
# and `commit_finalize` once their handlers exist.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "start_recording",
        "description": (
            "Open a new recording session for a skill scenario. By "
            "default auto-recovers a stale lock and force-aborts any "
            "existing active session so re-recording Just Works; pass "
            "force=false to honour an existing lock."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Skill name; skills/<skill_name>/SKILL.md must exist.",
                },
                "scenario_name": {
                    "type": "string",
                    "description": "Scenario folder name under skills/<skill>/evals/.",
                },
                "cc_session_id": {
                    "type": "string",
                    "description": "Optional cc session id from the MCP context.",
                },
                "parent_cc_session_id": {
                    "type": "string",
                    "description": (
                        "Optional override (M8); when omitted the server "
                        "reads CLAUDE_CODE_SESSION_ID from the env. Used "
                        "by the hook to filter the parent cc's own noise."
                    ),
                },
                "force": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "If true (default), forcibly abort any existing "
                        "active session before starting. The aborted "
                        "session's staging dir is kept on disk. Set to "
                        "false to refuse when another session holds the "
                        "lock — useful for scripted flows that must not "
                        "clobber a parallel manual recording."
                    ),
                },
            },
            "required": ["skill_name", "scenario_name"],
        },
    },
    {
        "name": "finalize",
        "description": (
            "Stage A of finalize: turn rounds.jsonl + workspace into "
            "staged mock_rounds/ + baseline/ + LLM-drafted judge "
            "candidate list (markdown). Does NOT write under "
            "skills/<skill>/evals/ — that's commit_finalize (M4). "
            "Returns the candidate-list markdown for the user to "
            "review."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "workspace_mirror_from": {
                    "type": "string",
                    "description": (
                        "Optional (M9): absolute path of an external "
                        "directory whose contents are mirrored into the "
                        "session workspace before baseline snapshot. Use "
                        "this when the recorded child cc wrote artifacts "
                        "to the project tree (e.g. production/<skill>/) "
                        "instead of session_dir/workspace/."
                    ),
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "commit_finalize",
        "description": (
            "Stage B of finalize: take user feedback markdown on the "
            "candidate draft and move staging/ to "
            "skills/<skill>/evals/<scenario>/ with judge_prompt.md, "
            "assertions/recorded.yaml, scenario.yaml, mock_rounds/, "
            "baseline/. Auto-adds P3 double-insurance tool_call_count==0 "
            "assertions for every mocked external tool. Returns either "
            "{scenario_dir, files_written, warnings, scenario_yaml_path} "
            "on success, or {action: 'user_clarification', questions} "
            "when LLM hit ambiguous_intents or required fields "
            "(query/target_path) were not provided."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "user_feedback_md": {
                    "type": "string",
                    "description": (
                        "Free-text markdown feedback on the candidate "
                        "draft. See design §12.2 for the 4 expression "
                        "patterns the parser accepts."
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "If true (default), back up an existing scenario "
                        "dir to <dir>.bak.<ts> before writing. Set to "
                        "false to refuse the commit when the scenario "
                        "dir is non-empty."
                    ),
                },
            },
            "required": ["session_id", "user_feedback_md"],
        },
    },
    {
        "name": "abort",
        "description": (
            "Abort the recording session; removes staged data unless "
            "`keep_staging` is true. Always clears the active lock."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "keep_staging": {"type": "boolean", "default": False},
            },
            "required": ["session_id"],
        },
    },
]


# ── JSON-RPC envelope helpers ────────────────────────────────────────────


def _ok(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _tool_ok(payload: Any) -> dict:
    body = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return {
        "content": [{"type": "text", "text": body}],
        "isError": False,
    }


def _tool_err(error_kind: str, message: str, extra: Optional[dict] = None) -> dict:
    body: dict[str, Any] = {"error_kind": error_kind, "error": message}
    if extra:
        body.update(extra)
    return {
        "content": [
            {"type": "text", "text": json.dumps(body, ensure_ascii=False)}
        ],
        "isError": True,
    }


# ── tool dispatch ────────────────────────────────────────────────────────


def _call_start_recording(
    args: dict, *, repo_root: Optional[Path]
) -> dict:
    skill_name = args.get("skill_name")
    scenario_name = args.get("scenario_name")
    if not skill_name or not scenario_name:
        return _tool_err(
            "InvalidArguments",
            "start_recording requires non-empty skill_name and scenario_name",
        )
    # M8: cc 2.1.156 injects CLAUDE_CODE_SESSION_ID for every stdio MCP
    # server (= the calling cc's own session_id). Take it as the parent
    # so the hook can filter the parent's noise. Undocumented but stable
    # across upstream + codefuse forks at this version; falls back to
    # None when missing, in which case the hook degrades to "first round
    # wins" backfill.
    parent_cc_session_id = (
        args.get("parent_cc_session_id")
        or os.environ.get("CLAUDE_CODE_SESSION_ID")
        or None
    )
    try:
        sess = _session.start_session(
            skill_name=skill_name,
            scenario_name=scenario_name,
            cc_session_id=args.get("cc_session_id"),
            repo_root=repo_root,
            parent_cc_session_id=parent_cc_session_id,
            # Default force=True so re-recording (e.g. user closed last
            # cc window, opens a new one) Just Works without waiting for
            # the 10m stale heuristic. Old session's staging is kept on
            # disk for inspection. Pass force=False to honour an existing
            # active lock (use case: external scripts that don't want to
            # clobber a parallel manual session).
            force=bool(args.get("force", True)),
        )
    except SkillNotFound as e:
        return _tool_err("SkillNotFound", str(e))
    except SessionAlreadyActive as e:
        return _tool_err(
            "SessionAlreadyActive",
            str(e),
            extra={"active_session_id": e.active_session_id},
        )
    except RecorderError as e:
        return _tool_err(type(e).__name__, str(e))
    except OSError as e:
        return _tool_err("SentinelWriteFailure", f"recorder root unwritable: {e}")

    result = {
        "session_id": sess.session_id,
        "recording_dir": sess.recording_dir,
        "started_at": sess.started_at,
        "parent_cc_session_id": sess.parent_cc_session_id,
    }

    # Live-trace daemon (best-effort; never blocks the recording).
    try:
        from one_context.recorder import daemon as _daemon
        _daemon.purge_dead_daemons()
        info = _daemon.spawn_daemon(sess.session_id)
        result["live_url"] = info.get("url")
        # macOS auto-open. Failure is silent — user can copy live_url.
        url = info.get("url")
        if url:
            try:
                import subprocess as _sp
                _sp.run(["open", url], check=False, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            except (OSError, FileNotFoundError):
                pass
    except Exception as e:
        result["live_url_error"] = f"{type(e).__name__}: {e}"

    return _tool_ok(result)


def _call_finalize(args: dict, *, repo_root: Optional[Path]) -> dict:
    session_id = args.get("session_id")
    if not session_id:
        return _tool_err("InvalidArguments", "finalize requires session_id")
    try:
        draft_md = _finalize.finalize_session(
            session_id,
            workspace_mirror_from=args.get("workspace_mirror_from") or None,
            repo_root=repo_root,
        )
    except SessionNotFound as e:
        return _tool_err("SessionNotFound", str(e))
    except SessionWrongState as e:
        return _tool_err("SessionWrongState", str(e))
    except RecorderError as e:
        return _tool_err(type(e).__name__, str(e))
    except Exception as e:
        # finalize swallows LLM failures into the markdown; anything that
        # bubbles up here is a programming bug worth surfacing.
        return _tool_err("FinalizeFailure", f"{type(e).__name__}: {e}")
    return _tool_ok(draft_md)


def _call_abort(args: dict) -> dict:
    session_id = args.get("session_id")
    if not session_id:
        return _tool_err("InvalidArguments", "abort requires session_id")
    try:
        out = _session.abort_session(
            session_id, keep_staging=bool(args.get("keep_staging", False))
        )
    except SessionNotFound as e:
        return _tool_err("SessionNotFound", str(e))
    except RecorderError as e:
        return _tool_err(type(e).__name__, str(e))
    return _tool_ok(out)


def _call_commit_finalize(args: dict, *, repo_root: Optional[Path]) -> dict:
    session_id = args.get("session_id")
    user_feedback_md = args.get("user_feedback_md")
    if not session_id or user_feedback_md is None:
        return _tool_err(
            "InvalidArguments",
            "commit_finalize requires session_id and user_feedback_md",
        )
    try:
        out = _commit_finalize.commit_finalize_session(
            session_id,
            user_feedback_md,
            # Default overwrite=True so re-recording the same
            # (skill, scenario) auto-backs-up the old dir to
            # <scenario>.bak.<ts>/ instead of erroring out. The user's
            # recording intent is "this is the new ground truth"; the
            # backup keeps the old version recoverable.
            overwrite=bool(args.get("overwrite", True)),
            repo_root=repo_root,
        )
    except SessionNotFound as e:
        return _tool_err("SessionNotFound", str(e))
    except SessionWrongState as e:
        return _tool_err("SessionWrongState", str(e))
    except InvalidFinalizeFeedback as e:
        return _tool_err(
            "InvalidFinalizeFeedback",
            str(e),
            extra={"unknown_ids": e.unknown_ids},
        )
    except TargetPathNotFound as e:
        return _tool_err(
            "TargetPathNotFound",
            str(e),
            extra={"target_path": e.target_path},
        )
    except EmptyTargetPath as e:
        return _tool_err(
            "EmptyTargetPath",
            str(e),
            extra={"target_path": e.target_path},
        )
    except ScenarioDirConflict as e:
        return _tool_err(
            "ScenarioDirConflict",
            str(e),
            extra={"existing": str(e.existing)},
        )
    except CommitFailure as e:
        return _tool_err(
            "CommitFailure",
            str(e),
            extra={"reason": e.reason},
        )
    except RecorderError as e:
        return _tool_err(type(e).__name__, str(e))
    except ValueError as e:
        # scenario / assertions schema validation failures bubble here.
        return _tool_err("SchemaValidationFailure", str(e))
    return _tool_ok(out)


def _dispatch_tool(name: str, args: dict, *, repo_root: Optional[Path]) -> dict:
    if name == "start_recording":
        return _call_start_recording(args, repo_root=repo_root)
    if name == "finalize":
        return _call_finalize(args, repo_root=repo_root)
    if name == "commit_finalize":
        return _call_commit_finalize(args, repo_root=repo_root)
    if name == "abort":
        return _call_abort(args)
    return _tool_err("UnknownTool", f"unknown tool: {name!r}")


# ── top-level JSON-RPC handler ───────────────────────────────────────────


def handle_request(
    payload: dict, *, repo_root: Optional[Path] = None
) -> Optional[dict]:
    """Dispatch one JSON-RPC request; return response dict or None.

    Returns None for notifications (no `id`), which the stdio loop drops.
    """
    method = payload.get("method")
    req_id = payload.get("id")

    # MCP notification — fired by cc after `initialize` succeeds.
    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return _ok(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "tools/list":
        return _ok(req_id, {"tools": TOOLS})

    if method == "tools/call":
        params = payload.get("params") or {}
        tool_name = params.get("name", "")
        args = params.get("arguments") or {}
        return _ok(req_id, _dispatch_tool(tool_name, args, repo_root=repo_root))

    # Ping is a common MCP keepalive; reply empty result.
    if method == "ping":
        return _ok(req_id, {})

    return _err(req_id, -32601, f"method not found: {method!r}")


def main() -> None:  # pragma: no cover - exercised by cc integration in M6
    """Stdio loop entry. Reads one JSON object per stdin line."""
    repo_root = Path(os.environ.get("ONECXT_RECORDER_REPO_ROOT", os.getcwd()))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(payload, repo_root=repo_root)
        if resp is None:
            continue
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    main()
