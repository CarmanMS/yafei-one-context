"""Hook payload → rounds.jsonl writer (Phase 2.8 M2).

cc fires `PostToolUse` and `PostToolUseFailure` hooks for every tool
invocation (see `recording-hook-spike-result.md`). The project-level
`.claude/settings.local.json` registers a thin shebang script
(`packages/one-context/scripts/onecxt-recorder-hook.py`) that pipes the
stdin payload into `process_hook` below.

Design contract (`recording-mode-design.md` §6.4 / §12.5 / §12.8):

1. **No-op when not recording**: the hook is registered permanently; it
   reads `active.json` on each call and silently exits when no session
   is in the `recording` state. This avoids hot-mutating
   `.claude/settings.local.json` from `start_recording` / `abort`
   (simpler crash recovery + no JSON race conditions); the per-call
   overhead is the cost of one `os.stat` on `active.json`, dwarfed by
   cc's own tool latency.
2. **External tools only** (`session.is_external_tool` single source):
   `WebFetch / WebSearch / Bash / mcp__*` get written; local tools
   (`Read / Write / Edit / Grep / ...`) are not — they re-run live during
   replay (design §1 row "录制 IO 边界").
3. **Field rename**: cc emits `tool_response`; `MockRound` expects
   `tool_result`. The jsonl carries `tool_result` so finalize can YAML it
   out without a second translation pass.
4. **Large response recovery**: cc truncates `tool_response.stdout` at
   ~30 000 chars but persists the full body to
   `tool_response.persistedOutputPath`. We read that file when present so
   the recorded mock matches what the original tool produced.
5. **Failed rounds** (`PostToolUseFailure`): payload has no
   `tool_response` and adds `error` + `is_interrupt`. We still write a
   round (boundary_type `failed_tool`) carrying
   `tool_result = {"error": ..., "is_error": True}` so finalize can
   surface it as a real failure — F-03 ("errors 隐瞒") relies on this.
6. **Never raises**: any exception (disk full, malformed JSON, missing
   persisted file) is swallowed. The hook script always exits 0; a hook
   crash must never take down the cc main loop.

All path resolution goes through `session.recorder_root()` so the
`ONECXT_RECORDER_ROOT` env override works under test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Optional

from one_context.recorder.session import (
    SessionNotFound,
    get_active_session_id,
    is_external_tool,
    load_session,
    record_cc_session_id,
)

FAILURE_EVENT = "PostToolUseFailure"
SUCCESS_EVENT = "PostToolUse"
BoundaryType = Literal["local_tool", "mcp_call", "failed_tool"]
# TODO(step-debug): 当前 3 类来自 PostToolUse hook 视角。若引入 step-debug
# 能力（人工断点 / 逐轮回放 / 推理段可视化），需扩展到 round 视角：
# `inference`（纯推理段，hook 不可见，需 stream-json 解析）/
# `user_interaction`（cc 等待用户，hook 不可见）/
# `agent_call`（子 Agent 即 Task tool，当前被归到 `local_tool`，粒度不够）。
# 不在 eval 主线做，立项后再扩；参考 aihaasmonorepo/tools/skill-debug/
# src/skill_debug/models/__init__.py:517 的 5 类划分。


# ── id derivation (design §12.1) ────────────────────────────────────────


def _slugify_tool_name(tool_name: str) -> str:
    """`mcp__plugin_pw__browser_navigate` → `plugin-pw-browser-navigate`."""
    name = tool_name or "unknown"
    if name.startswith("mcp__"):
        name = name[len("mcp__"):]
    return name.replace("__", "-").lower() or "unknown"


def _canonical_input_hash(tool_input: Any) -> str:
    """sha256 prefix of canonicalized tool_input — disambiguates repeats."""
    try:
        body = json.dumps(
            tool_input, sort_keys=True, ensure_ascii=False, default=str
        )
    except (TypeError, ValueError):
        body = repr(tool_input)
    return hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()[:8]


def _next_round_seq(rounds_jsonl: Path) -> int:
    """Sequence = lines already in jsonl + 1 (1-based, 2-padded later)."""
    if not rounds_jsonl.exists():
        return 1
    n = 0
    try:
        with rounds_jsonl.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    n += 1
    except OSError:
        return 1
    return n + 1


def _derive_round_id(
    rounds_jsonl: Path, tool_name: str, tool_input: Any
) -> str:
    return (
        f"round-{_next_round_seq(rounds_jsonl):02d}"
        f"-{_slugify_tool_name(tool_name)}"
        f"-{_canonical_input_hash(tool_input)}"
    )


def _derive_boundary_type(tool_name: str, event_type: str) -> BoundaryType:
    if event_type == FAILURE_EVENT:
        return "failed_tool"
    if tool_name.startswith("mcp__"):
        return "mcp_call"
    return "local_tool"


# ── large response recovery (design §12.8 修 2) ─────────────────────────


def _resolve_full_tool_response(hook_payload: dict) -> Any:
    """Substitute `tool_response.stdout` with the persisted full body.

    cc caps `tool_response.stdout` at ~30 000 chars but writes the
    untruncated body to `tool_response.persistedOutputPath` (a file in
    `~/.claude/projects/<sid>/tool-results/<hash>.txt`). Recover it when
    the persisted size exceeds what we already have inline.

    Falls back to the raw `tool_response` on any read error.
    """
    tr = hook_payload.get("tool_response")
    if not isinstance(tr, dict):
        return tr
    persisted_path = tr.get("persistedOutputPath")
    if not persisted_path:
        return tr
    try:
        p = Path(persisted_path)
        if not p.exists():
            return tr
        persisted_size = tr.get("persistedOutputSize") or 0
        stdout_str = tr.get("stdout") if isinstance(tr.get("stdout"), str) else ""
        if persisted_size and persisted_size <= len(stdout_str):
            return tr  # inline already complete; no recovery needed
        full = p.read_text(encoding="utf-8", errors="replace")
        return {**tr, "stdout": full, "_recorder_resolved_persisted": True}
    except OSError:
        return tr


# ── round writer ────────────────────────────────────────────────────────


def write_round(
    hook_payload: dict,
    event_type: str,
    session_dir: Path,
    *,
    parent_cc_session_id: Optional[str] = None,
    recorder_session_id: Optional[str] = None,
    backfill_cc_session_id: bool = False,
) -> bool:
    """Append one round record to `<session_dir>/rounds.jsonl`.

    Returns True iff a round was actually written. Never raises — hook
    invariant: the script always exits 0.

    M6 (replaces M8 parent filter — see below):
    - `parent_cc_session_id`: kept in the signature for backwards-compat
      but NO LONGER used for filtering. M8's original design assumed
      onecxt-record spawned a child cc to drive the recorded skill, so
      `round.session_id == parent_cc_session_id` meant "parent cc's own
      management noise — drop". In practice the skill keeps the user
      in the parent cc (SKILL.md Step 1.5 "立刻退场"), so every business
      round's session_id IS parent_cc_session_id. The old filter dropped
      100% of business rounds → 0-round empty recordings (the a8fa1c6e
      session bug, 2026-06-02).
    - `recorder_session_id` + `backfill_cc_session_id`: when True, the
      first business round's session_id is written back into session.json's
      `cc_session_id` field so finalize can filter by it. In same-cc mode
      this backfills parent_cc_session_id (correct: that IS the cc whose
      transcript finalize reads).

    The only real noise is the recorder skill's own MCP tool calls
    (start_recording / finalize / commit / abort). Recording those
    creates a self-referential loop. We filter by tool_name, not by
    cc_session_id. The MCP server is registered as `onecxt-recorder`
    in `.mcp.json`, so cc emits `mcp__onecxt-recorder__*` — match both
    hyphen and legacy underscore forms.
    """
    try:
        tool_name = hook_payload.get("tool_name", "") or ""
        if not is_external_tool(tool_name):
            return False  # local tools (Read/Edit/...) are not recorded

        if tool_name.startswith(("mcp__onecxt-recorder__", "mcp__onecxt_recorder__")):
            return False

        round_cc_session_id = hook_payload.get("session_id")

        rounds_jsonl = session_dir / "rounds.jsonl"
        tool_input = hook_payload.get("tool_input") or {}
        round_id = _derive_round_id(rounds_jsonl, tool_name, tool_input)

        if event_type == FAILURE_EVENT:
            err_msg = hook_payload.get("error", "<no error message>")
            tool_result: Any = {"error": err_msg, "is_error": True}
            failure_extra: dict | None = {
                "error": hook_payload.get("error"),
                "is_interrupt": bool(hook_payload.get("is_interrupt", False)),
            }
        else:
            tool_result = _resolve_full_tool_response(hook_payload)
            failure_extra = None

        record: dict[str, Any] = {
            "round_id": round_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_result": tool_result,
            "assistant_thinking": "",
            "boundary_type": _derive_boundary_type(tool_name, event_type),
            "event_type": event_type,
            "cc_session_id": hook_payload.get("session_id"),
        }
        if failure_extra is not None:
            record["_failure"] = failure_extra

        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        rounds_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with rounds_jsonl.open("a", encoding="utf-8") as f:
            f.write(line)

        # M8: first non-parent round wins — backfill cc_session_id so
        # finalize can filter rounds.jsonl by it without a manual patch.
        if (
            backfill_cc_session_id
            and recorder_session_id
            and round_cc_session_id
        ):
            record_cc_session_id(recorder_session_id, round_cc_session_id)

        return True
    except Exception:
        # Invariant: hooks must not crash cc. Swallow & exit 0.
        return False


# ── top-level entry from hook script ────────────────────────────────────


def process_hook(stdin_text: str) -> bool:
    """Dispatch one hook stdin payload. Returns True iff a round wrote.

    No-op (returns False) when:
    - stdin is empty / non-JSON / not a dict
    - no active session (active.json missing)
    - active session not in `recording` state
    - hook payload's tool_name is a local tool

    Never raises.
    """
    try:
        if not stdin_text or not stdin_text.strip():
            return False
        try:
            payload = json.loads(stdin_text)
        except (json.JSONDecodeError, ValueError, TypeError):
            return False
        if not isinstance(payload, dict):
            return False

        event_type = payload.get("hook_event_name", SUCCESS_EVENT)

        try:
            active_session_id = get_active_session_id()
        except Exception:
            return False
        if not active_session_id:
            return False

        try:
            session = load_session(active_session_id)
        except (SessionNotFound, Exception):
            return False

        if session.status != "recording":
            return False

        return write_round(
            payload,
            event_type,
            Path(session.recording_dir),
            parent_cc_session_id=session.parent_cc_session_id,
            recorder_session_id=session.session_id,
            backfill_cc_session_id=session.cc_session_id is None,
        )
    except Exception:
        return False
