"""MCP server JSON-RPC dispatch tests (Phase 2.8 M1).

`handle_request` is a pure function so we can drive it with synthetic
JSON-RPC payloads instead of spawning a real cc subprocess. The full
stdio loop (`main`) lands in M6 with real cc integration tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from one_context.recorder import session as session_mod
from one_context.recorder.mcp_server import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    TOOLS,
    handle_request,
)


def _rpc(method: str, *, params: dict | None = None, req_id: Any = 1) -> dict:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _tool_body(resp: dict) -> dict:
    """Decode the JSON payload from a `tools/call` content[0].text reply."""
    content = resp["result"]["content"]
    assert content and content[0]["type"] == "text"
    return json.loads(content[0]["text"])


# ── lifecycle methods ───────────────────────────────────────────────────


def test_initialize_returns_capabilities(recorder_tmp: Path) -> None:
    resp = handle_request(_rpc("initialize"))
    assert resp is not None
    result = resp["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == SERVER_NAME
    assert "tools" in result["capabilities"]


def test_notifications_initialized_returns_none(recorder_tmp: Path) -> None:
    payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert handle_request(payload) is None


def test_tools_list_advertises_m1_m3_tools(recorder_tmp: Path) -> None:
    resp = handle_request(_rpc("tools/list"))
    assert resp is not None
    names = {t["name"] for t in resp["result"]["tools"]}
    # M1 + M3 surface. commit_finalize lands in M4.
    assert {"start_recording", "finalize", "abort"} <= names
    assert TOOLS  # registry not empty


def test_unknown_method_returns_jsonrpc_error(recorder_tmp: Path) -> None:
    resp = handle_request(_rpc("does/not/exist"))
    assert resp is not None
    assert resp["error"]["code"] == -32601


def test_ping_replies_empty(recorder_tmp: Path) -> None:
    resp = handle_request(_rpc("ping"))
    assert resp is not None
    assert resp["result"] == {}


# ── tools/call: start_recording ─────────────────────────────────────────


def test_start_recording_via_mcp_succeeds(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo",
                    "scenario_name": "scn-1",
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert resp is not None
    assert resp["result"]["isError"] is False
    body = _tool_body(resp)
    assert "session_id" in body and body["session_id"]
    assert body["recording_dir"].startswith(str(recorder_tmp))
    assert session_mod.get_active_session_id() == body["session_id"]


def test_start_recording_skill_not_found_returns_tool_error(
    recorder_tmp: Path, tmp_path: Path
) -> None:
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "ghost",
                    "scenario_name": "scn",
                },
            },
        ),
        repo_root=empty_repo,
    )
    assert resp is not None
    result = resp["result"]
    assert result["isError"] is True
    body = _tool_body(resp)
    assert body["error_kind"] == "SkillNotFound"


def test_start_recording_double_start_with_force_false_returns_already_active(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """force=False (strict mode) preserves the original error semantics.

    NB: as of M5, the default behaviour is force=True which auto-clobbers
    the active lock. This test pins the explicit opt-out path.
    """
    first = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {"skill_name": "demo", "scenario_name": "a"},
            },
        ),
        repo_root=repo_with_skill,
    )
    assert first and first["result"]["isError"] is False
    first_id = _tool_body(first)["session_id"]

    second = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo", "scenario_name": "b",
                    "force": False,
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert second is not None
    body = _tool_body(second)
    assert second["result"]["isError"] is True
    assert body["error_kind"] == "SessionAlreadyActive"
    assert body["active_session_id"] == first_id


def test_start_recording_invalid_args_returns_tool_error(
    recorder_tmp: Path,
) -> None:
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {"skill_name": "", "scenario_name": ""},
            },
        ),
    )
    assert resp is not None
    body = _tool_body(resp)
    assert resp["result"]["isError"] is True
    assert body["error_kind"] == "InvalidArguments"


# ── tools/call: abort ───────────────────────────────────────────────────


def test_abort_via_mcp_clears_active(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    started = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {"skill_name": "demo", "scenario_name": "scn"},
            },
        ),
        repo_root=repo_with_skill,
    )
    assert started is not None
    sid = _tool_body(started)["session_id"]

    aborted = handle_request(
        _rpc(
            "tools/call",
            params={"name": "abort", "arguments": {"session_id": sid}},
        )
    )
    assert aborted is not None
    assert aborted["result"]["isError"] is False
    body = _tool_body(aborted)
    assert "aborted_at" in body
    assert body["kept_paths"] == []
    assert session_mod.get_active_session_id() is None


def test_abort_unknown_session_returns_tool_error(
    recorder_tmp: Path,
) -> None:
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "abort",
                "arguments": {"session_id": "ghost-id"},
            },
        )
    )
    assert resp is not None
    body = _tool_body(resp)
    assert resp["result"]["isError"] is True
    assert body["error_kind"] == "SessionNotFound"


# ── tools/call: finalize (M3) ───────────────────────────────────────────


def test_finalize_via_mcp_returns_markdown(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """finalize tool call dispatches into finalize_session and returns
    the markdown candidate list as the content text body."""
    from one_context.recorder import finalize as finalize_mod

    monkeypatch.setattr(
        finalize_mod, "finalize_session",
        lambda sid, **_: "# fake draft\n\n### D1: x\n### F1: y\n"
    )
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "finalize",
                "arguments": {"session_id": "anything"},
            },
        )
    )
    assert resp is not None
    assert resp["result"]["isError"] is False
    text = resp["result"]["content"][0]["text"]
    assert "fake draft" in text
    assert "### D1:" in text


def test_finalize_via_mcp_surfaces_wrong_state_error(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from one_context.recorder import finalize as finalize_mod
    from one_context.recorder.session import SessionWrongState

    def boom(sid: str, **_: object) -> str:
        raise SessionWrongState("not recording")

    monkeypatch.setattr(finalize_mod, "finalize_session", boom)
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "finalize",
                "arguments": {"session_id": "x"},
            },
        )
    )
    assert resp is not None
    body = _tool_body(resp)
    assert resp["result"]["isError"] is True
    assert body["error_kind"] == "SessionWrongState"


def test_finalize_via_mcp_requires_session_id(recorder_tmp: Path) -> None:
    resp = handle_request(
        _rpc(
            "tools/call",
            params={"name": "finalize", "arguments": {}},
        )
    )
    assert resp is not None
    body = _tool_body(resp)
    assert resp["result"]["isError"] is True
    assert body["error_kind"] == "InvalidArguments"


def test_unknown_tool_call_returns_tool_error(recorder_tmp: Path) -> None:
    # `finalize` exists from M3 onward — use a fake name for this check.
    resp = handle_request(
        _rpc(
            "tools/call",
            params={"name": "definitely-not-a-tool", "arguments": {}},
        )
    )
    assert resp is not None
    body = _tool_body(resp)
    assert resp["result"]["isError"] is True
    assert body["error_kind"] == "UnknownTool"


# ── M8: parent_cc_session_id from env / explicit arg ───────────────────


def test_start_recording_auto_picks_parent_from_env(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "env-parent-cc")
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo",
                    "scenario_name": "scn",
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert resp and resp["result"]["isError"] is False
    body = _tool_body(resp)
    assert body["parent_cc_session_id"] == "env-parent-cc"
    sess = session_mod.load_session(body["session_id"])
    assert sess.parent_cc_session_id == "env-parent-cc"


def test_start_recording_explicit_arg_overrides_env(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "env-parent")
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo",
                    "scenario_name": "scn",
                    "parent_cc_session_id": "arg-parent",
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert resp and resp["result"]["isError"] is False
    assert _tool_body(resp)["parent_cc_session_id"] == "arg-parent"


def test_finalize_via_mcp_passes_workspace_mirror_from(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M9: finalize tool forwards workspace_mirror_from to finalize_session."""
    from one_context.recorder import finalize as finalize_mod

    captured: dict = {}

    def fake_finalize(sid: str, **kwargs) -> str:
        captured["sid"] = sid
        captured["kwargs"] = kwargs
        return "# ok"

    monkeypatch.setattr(finalize_mod, "finalize_session", fake_finalize)
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "finalize",
                "arguments": {
                    "session_id": "s1",
                    "workspace_mirror_from": "/tmp/some-real-dir",
                },
            },
        )
    )
    assert resp and resp["result"]["isError"] is False
    assert captured["sid"] == "s1"
    assert captured["kwargs"]["workspace_mirror_from"] == "/tmp/some-real-dir"


def test_finalize_via_mcp_empty_workspace_mirror_from_treated_as_none(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty string mirror_from coerced to None (don't trigger mirror)."""
    from one_context.recorder import finalize as finalize_mod

    captured: dict = {}

    def fake_finalize(sid: str, **kwargs) -> str:
        captured.update(kwargs)
        return "# ok"

    monkeypatch.setattr(finalize_mod, "finalize_session", fake_finalize)
    handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "finalize",
                "arguments": {
                    "session_id": "s1",
                    "workspace_mirror_from": "",
                },
            },
        )
    )
    assert captured["workspace_mirror_from"] is None


def test_commit_finalize_overwrite_defaults_to_true(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When client omits `overwrite`, mcp_server must pass True to
    commit_finalize_session so re-recording auto-backs-up the old dir
    instead of erroring out."""
    from one_context.recorder import commit_finalize as commit_mod

    captured: dict = {}

    def fake_commit(sid: str, feedback: str, **kwargs) -> dict:
        captured.update(kwargs)
        return {
            "scenario_dir": "/tmp/x", "files_written": [],
            "warnings": [], "scenario_yaml_path": "/tmp/x/scenario.yaml",
            "backup_path": None,
        }

    monkeypatch.setattr(commit_mod, "commit_finalize_session", fake_commit)
    handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "commit_finalize",
                "arguments": {
                    "session_id": "s1",
                    "user_feedback_md": "全收",
                    # NOTE: deliberately NOT passing overwrite
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert captured["overwrite"] is True, (
        "Regression: re-recording the same scenario must auto-overwrite "
        "(with .bak.<ts> backup) so user doesn't have to manually delete "
        "the old scenario dir between recordings"
    )


def test_commit_finalize_explicit_overwrite_false_honoured(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit `overwrite: false` from client must still win over default."""
    from one_context.recorder import commit_finalize as commit_mod

    captured: dict = {}

    def fake_commit(sid: str, feedback: str, **kwargs) -> dict:
        captured.update(kwargs)
        return {
            "scenario_dir": "/tmp/x", "files_written": [],
            "warnings": [], "scenario_yaml_path": "/tmp/x/scenario.yaml",
            "backup_path": None,
        }

    monkeypatch.setattr(commit_mod, "commit_finalize_session", fake_commit)
    handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "commit_finalize",
                "arguments": {
                    "session_id": "s1",
                    "user_feedback_md": "全收",
                    "overwrite": False,
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert captured["overwrite"] is False


def test_start_recording_default_force_clobbers_active_lock(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """MCP start_recording defaults to force=True so re-recording works
    even when a prior fresh session sits in active.json."""
    # Open one session through the normal path so active.json is set.
    resp1 = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo",
                    "scenario_name": "first",
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert resp1 and resp1["result"]["isError"] is False

    # Without our force=True default, this second call would error out.
    resp2 = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo",
                    "scenario_name": "second",
                    # NOTE: force NOT passed — relies on True default
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert resp2 and resp2["result"]["isError"] is False, (
        "Regression: re-recording must succeed without manual lock clear"
    )


def test_start_recording_force_false_honours_existing_lock(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """Explicit force=false from client preserves strict-block behaviour."""
    handle_request(
        _rpc("tools/call", params={
            "name": "start_recording",
            "arguments": {
                "skill_name": "demo", "scenario_name": "first",
            },
        }),
        repo_root=repo_with_skill,
    )
    resp = handle_request(
        _rpc("tools/call", params={
            "name": "start_recording",
            "arguments": {
                "skill_name": "demo", "scenario_name": "second",
                "force": False,
            },
        }),
        repo_root=repo_with_skill,
    )
    assert resp and resp["result"]["isError"] is True
    body = _tool_body(resp)
    assert body["error_kind"] == "SessionAlreadyActive"


def test_start_recording_no_env_no_arg_leaves_parent_none(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    resp = handle_request(
        _rpc(
            "tools/call",
            params={
                "name": "start_recording",
                "arguments": {
                    "skill_name": "demo",
                    "scenario_name": "scn",
                },
            },
        ),
        repo_root=repo_with_skill,
    )
    assert resp and resp["result"]["isError"] is False
    body = _tool_body(resp)
    assert body["parent_cc_session_id"] is None
