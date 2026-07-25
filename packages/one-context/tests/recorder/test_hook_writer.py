"""hook_writer tests (Phase 2.8 M2).

Covers the contract from `recording-mode-design.md` §6.4 / §12.5 /
§12.8:

- external-tool filter (`is_external_tool` single source)
- field rename `tool_response → tool_result`
- large-response recovery via `persistedOutputPath`
- `PostToolUseFailure` event → boundary_type `failed_tool` + `_failure`
  metadata
- no active session → no-op (no write, no raise)
- crash-safe: malformed JSON, missing persisted file, disk error never
  raise
- round_id naming (`round-NN-<slug>-<hash8>`) sequences + uniqueness
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.recorder.hook_writer import (
    FAILURE_EVENT,
    SUCCESS_EVENT,
    _canonical_input_hash,
    _derive_round_id,
    _resolve_full_tool_response,
    _slugify_tool_name,
    process_hook,
    write_round,
)
from one_context.recorder.session import (
    abort_session,
    start_session,
)


# ── helpers ─────────────────────────────────────────────────────────────


def _read_rounds(session_dir: Path) -> list[dict]:
    jsonl = session_dir / "rounds.jsonl"
    if not jsonl.exists():
        return []
    out = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _post_tool_use(
    tool_name: str,
    tool_input: dict | None = None,
    tool_response=None,
    session_id: str = "cc-sess-xyz",
) -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": SUCCESS_EVENT,
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "tool_response": tool_response if tool_response is not None else "",
    }


def _post_tool_use_failure(
    tool_name: str,
    tool_input: dict | None = None,
    error: str = "boom",
    is_interrupt: bool = False,
    session_id: str = "cc-sess-xyz",
) -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": FAILURE_EVENT,
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "error": error,
        "is_interrupt": is_interrupt,
    }


# ── slugify + hash helpers ──────────────────────────────────────────────


def test_slugify_strips_mcp_prefix_and_lowercases() -> None:
    assert _slugify_tool_name("Bash") == "bash"
    assert _slugify_tool_name("WebFetch") == "webfetch"
    assert (
        _slugify_tool_name("mcp__plugin_playwright_playwright__browser_navigate")
        == "plugin_playwright_playwright-browser_navigate"
    )
    assert (
        _slugify_tool_name("mcp__onecxt_recorder__start_recording")
        == "onecxt_recorder-start_recording"
    )
    assert _slugify_tool_name("") == "unknown"


def test_canonical_input_hash_stable_and_short() -> None:
    h1 = _canonical_input_hash({"a": 1, "b": 2})
    h2 = _canonical_input_hash({"b": 2, "a": 1})  # key order independent
    assert h1 == h2
    assert len(h1) == 8
    # Different inputs → different hashes (overwhelmingly likely).
    assert _canonical_input_hash({"a": 1}) != _canonical_input_hash({"a": 2})


def test_derive_round_id_sequence_increments(tmp_path: Path) -> None:
    jsonl = tmp_path / "rounds.jsonl"
    rid1 = _derive_round_id(jsonl, "Bash", {"command": "ls"})
    assert rid1.startswith("round-01-bash-")
    jsonl.write_text(rid1 + "\n", encoding="utf-8")
    rid2 = _derive_round_id(jsonl, "WebFetch", {"url": "x"})
    assert rid2.startswith("round-02-webfetch-")


# ── _resolve_full_tool_response ────────────────────────────────────────


def test_resolve_full_returns_non_dict_unchanged() -> None:
    assert _resolve_full_tool_response({"tool_response": "plain"}) == "plain"
    assert _resolve_full_tool_response({"tool_response": ["a", "b"]}) == ["a", "b"]
    assert _resolve_full_tool_response({"tool_response": None}) is None


def test_resolve_full_reads_persisted_when_inline_truncated(
    tmp_path: Path,
) -> None:
    persisted = tmp_path / "full.txt"
    full_body = "x" * 100_000
    persisted.write_text(full_body, encoding="utf-8")
    payload = {
        "tool_response": {
            "stdout": "x" * 29_999,  # cc truncation
            "stderr": "",
            "interrupted": False,
            "persistedOutputPath": str(persisted),
            "persistedOutputSize": 100_000,
        }
    }
    out = _resolve_full_tool_response(payload)
    assert isinstance(out, dict)
    assert out["stdout"] == full_body
    assert out["_recorder_resolved_persisted"] is True


def test_resolve_full_falls_back_when_persisted_missing(tmp_path: Path) -> None:
    payload = {
        "tool_response": {
            "stdout": "head only",
            "persistedOutputPath": str(tmp_path / "does-not-exist.txt"),
            "persistedOutputSize": 100_000,
        }
    }
    out = _resolve_full_tool_response(payload)
    assert isinstance(out, dict)
    assert out["stdout"] == "head only"
    assert "_recorder_resolved_persisted" not in out


def test_resolve_full_no_persisted_path_returns_tr_as_is() -> None:
    tr = {"stdout": "small", "stderr": ""}
    assert _resolve_full_tool_response({"tool_response": tr}) == tr


# ── write_round filter behaviour ───────────────────────────────────────


def test_write_round_local_tool_is_noop(tmp_path: Path) -> None:
    session_dir = tmp_path
    (session_dir / "rounds.jsonl").touch()
    assert write_round(_post_tool_use("Read", {"file_path": "/x"}), SUCCESS_EVENT, session_dir) is False
    assert write_round(_post_tool_use("Edit"), SUCCESS_EVENT, session_dir) is False
    assert write_round(_post_tool_use("Glob"), SUCCESS_EVENT, session_dir) is False
    assert _read_rounds(session_dir) == []


def test_write_round_external_tool_writes(tmp_path: Path) -> None:
    session_dir = tmp_path
    payload = _post_tool_use(
        "Bash",
        {"command": "ls /etc"},
        {"stdout": "passwd\nhosts\n", "stderr": "", "interrupted": False},
    )
    ok = write_round(payload, SUCCESS_EVENT, session_dir)
    assert ok is True
    rounds = _read_rounds(session_dir)
    assert len(rounds) == 1
    r = rounds[0]
    assert r["tool_name"] == "Bash"
    assert r["tool_input"] == {"command": "ls /etc"}
    assert r["tool_result"]["stdout"] == "passwd\nhosts\n"
    assert r["boundary_type"] == "local_tool"
    assert r["event_type"] == SUCCESS_EVENT
    assert r["cc_session_id"] == "cc-sess-xyz"
    assert r["round_id"].startswith("round-01-bash-")
    assert "_failure" not in r


def test_write_round_mcp_tool_boundary_type(tmp_path: Path) -> None:
    payload = _post_tool_use(
        "mcp__plugin_playwright_playwright__browser_console_messages",
        {},
        [{"type": "log", "text": "hi"}],
    )
    assert write_round(payload, SUCCESS_EVENT, tmp_path) is True
    r = _read_rounds(tmp_path)[0]
    assert r["boundary_type"] == "mcp_call"
    assert r["round_id"].startswith(
        "round-01-plugin_playwright_playwright-browser_console_messages-"
    )


def test_write_round_large_response_recovers_persisted(
    tmp_path: Path,
) -> None:
    persisted = tmp_path / "big.txt"
    full = "y" * 80_000
    persisted.write_text(full, encoding="utf-8")
    payload = _post_tool_use(
        "Bash",
        {"command": "cat big.txt"},
        {
            "stdout": "y" * 29_999,
            "stderr": "",
            "interrupted": False,
            "persistedOutputPath": str(persisted),
            "persistedOutputSize": 80_000,
        },
    )
    assert write_round(payload, SUCCESS_EVENT, tmp_path) is True
    r = _read_rounds(tmp_path)[0]
    assert r["tool_result"]["stdout"] == full
    assert r["tool_result"]["_recorder_resolved_persisted"] is True


def test_write_round_failure_event_records_failed_round(
    tmp_path: Path,
) -> None:
    payload = _post_tool_use_failure(
        "WebFetch",
        {"url": "https://blocked.example"},
        error="Unable to verify if domain is permitted",
        is_interrupt=False,
    )
    assert write_round(payload, FAILURE_EVENT, tmp_path) is True
    r = _read_rounds(tmp_path)[0]
    assert r["boundary_type"] == "failed_tool"
    assert r["event_type"] == FAILURE_EVENT
    assert r["tool_result"]["is_error"] is True
    assert "Unable to verify" in r["tool_result"]["error"]
    assert r["_failure"]["error"] == "Unable to verify if domain is permitted"
    assert r["_failure"]["is_interrupt"] is False


def test_write_round_sequence_padding_and_disambiguation(
    tmp_path: Path,
) -> None:
    # Same tool name + same input twice → same hash → still unique by NN.
    payload = _post_tool_use("Bash", {"command": "date"}, {"stdout": "x"})
    write_round(payload, SUCCESS_EVENT, tmp_path)
    write_round(payload, SUCCESS_EVENT, tmp_path)
    write_round(payload, SUCCESS_EVENT, tmp_path)
    rounds = _read_rounds(tmp_path)
    ids = [r["round_id"] for r in rounds]
    assert len(set(ids)) == 3
    assert ids[0].startswith("round-01-bash-")
    assert ids[1].startswith("round-02-bash-")
    assert ids[2].startswith("round-03-bash-")


def test_write_round_never_raises_on_disk_error(tmp_path: Path) -> None:
    # session_dir is a *file*, not a dir — mkdir + open will fail.
    bogus = tmp_path / "not-a-dir"
    bogus.write_text("", encoding="utf-8")
    # Must not raise; returns False.
    payload = _post_tool_use("Bash", {"command": "ls"}, {"stdout": "ok"})
    assert write_round(payload, SUCCESS_EVENT, bogus) is False


# ── process_hook integration ───────────────────────────────────────────


def test_process_hook_no_active_session_is_noop(
    recorder_tmp: Path,
) -> None:
    payload = _post_tool_use("Bash", {"command": "ls"}, {"stdout": "x"})
    assert process_hook(json.dumps(payload)) is False
    # no session, so no jsonl anywhere
    assert not (recorder_tmp / "active.json").exists()


def test_process_hook_writes_when_recording(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    try:
        payload = _post_tool_use("Bash", {"command": "echo hi"}, {"stdout": "hi"})
        assert process_hook(json.dumps(payload)) is True
        rounds = _read_rounds(Path(sess.recording_dir))
        assert len(rounds) == 1
        assert rounds[0]["tool_name"] == "Bash"
    finally:
        abort_session(sess.session_id)


def test_process_hook_filters_local_tools_when_recording(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    try:
        payload = _post_tool_use("Read", {"file_path": "/etc/hostname"})
        assert process_hook(json.dumps(payload)) is False
        assert _read_rounds(Path(sess.recording_dir)) == []
    finally:
        abort_session(sess.session_id)


def test_process_hook_handles_malformed_json(recorder_tmp: Path) -> None:
    assert process_hook("not-json-at-all{") is False
    assert process_hook("") is False
    assert process_hook("   ") is False
    assert process_hook("[]") is False  # JSON, but not a dict


def test_process_hook_routes_failure_event(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    try:
        payload = _post_tool_use_failure(
            "WebFetch", {"url": "https://x"}, error="proxy denied"
        )
        assert process_hook(json.dumps(payload)) is True
        r = _read_rounds(Path(sess.recording_dir))[0]
        assert r["boundary_type"] == "failed_tool"
        assert r["_failure"]["error"] == "proxy denied"
    finally:
        abort_session(sess.session_id)


def test_process_hook_skips_when_session_not_recording(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """If active.json says recording but session.json status = aborted, no-op."""
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    # Forcibly desync: keep active.json but flip session status on disk.
    from one_context.recorder.session import load_session, save_session

    s = load_session(sess.session_id)
    s.status = "aborted"
    save_session(s)

    payload = _post_tool_use("Bash", {"command": "ls"}, {"stdout": "x"})
    assert process_hook(json.dumps(payload)) is False
    assert _read_rounds(Path(sess.recording_dir)) == []
    # cleanup
    abort_session(sess.session_id)


# ── M6: tool-name filter (recorder MCP echoes) + same-cc support ───────


def test_process_hook_drops_recorder_mcp_echoes(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """Hook silently drops recorder MCP echoes (skill driving its own
    state machine — recording them creates a self-ref loop). The MCP
    server is registered as `onecxt-recorder` so real cc payloads carry
    `mcp__onecxt-recorder__*`; the legacy underscore form is also
    accepted for back-compat. Regression for the f7402676 bug where the
    hyphen form leaked through the filter."""
    sess = start_session(
        "demo", "scn", repo_root=repo_with_skill,
        parent_cc_session_id="parent-cc",
    )
    try:
        for name in (
            "mcp__onecxt-recorder__start_recording",
            "mcp__onecxt-recorder__finalize",
            "mcp__onecxt_recorder__finalize",
        ):
            echo = _post_tool_use(
                name,
                {"session_id": "x"},
                {"ok": True},
                session_id="parent-cc",
            )
            assert process_hook(json.dumps(echo)) is False, name
        assert _read_rounds(Path(sess.recording_dir)) == []
    finally:
        abort_session(sess.session_id)


def test_process_hook_records_round_when_round_cc_equals_parent(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """Same-cc mode: user runs the recorded skill in the SAME cc that
    drives onecxt-record. Every round's session_id == parent_cc_session_id;
    the old M8 filter dropped 100% of those (the a8fa1c6e bug — 0 rounds
    recorded despite working skill execution). M6 keeps them."""
    sess = start_session(
        "demo", "scn", repo_root=repo_with_skill,
        parent_cc_session_id="parent-cc",
    )
    try:
        payload = _post_tool_use(
            "WebFetch",
            {"url": "https://example.com"},
            {"body": "ok"},
            session_id="parent-cc",  # same as parent — old code dropped this
        )
        assert process_hook(json.dumps(payload)) is True
        rounds = _read_rounds(Path(sess.recording_dir))
        assert len(rounds) == 1
        assert rounds[0]["cc_session_id"] == "parent-cc"

        # Backfill must use parent-cc since that IS the cc whose
        # transcript finalize will read.
        from one_context.recorder.session import load_session
        assert load_session(sess.session_id).cc_session_id == "parent-cc"
    finally:
        abort_session(sess.session_id)


def test_process_hook_backfills_first_business_round_not_echo(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """First non-recorder-echo round wins the cc_session_id backfill.
    A preceding `mcp__onecxt-recorder__*` echo must NOT consume backfill."""
    sess = start_session(
        "demo", "scn", repo_root=repo_with_skill,
        parent_cc_session_id="parent-cc",
    )
    try:
        # Recorder echo first — must drop, no backfill.
        echo = _post_tool_use(
            "mcp__onecxt-recorder__start_recording",
            {"x": 1}, {"ok": True}, session_id="parent-cc",
        )
        assert process_hook(json.dumps(echo)) is False

        # Then a real business tool round.
        business = _post_tool_use(
            "Bash", {"command": "real"}, {"stdout": "ok"},
            session_id="some-cc",
        )
        assert process_hook(json.dumps(business)) is True

        rounds = _read_rounds(Path(sess.recording_dir))
        assert len(rounds) == 1
        assert rounds[0]["cc_session_id"] == "some-cc"

        from one_context.recorder.session import load_session
        assert load_session(sess.session_id).cc_session_id == "some-cc"

        # Subsequent business rounds must not re-trigger backfill.
        another = _post_tool_use(
            "Bash", {"command": "again"}, {"stdout": ""}, session_id="other-cc",
        )
        assert process_hook(json.dumps(another)) is True
        assert load_session(sess.session_id).cc_session_id == "some-cc"
    finally:
        abort_session(sess.session_id)


def test_process_hook_no_parent_falls_back_to_first_round_backfill(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """Without parent_cc_session_id, the first round's session_id wins."""
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    try:
        payload = _post_tool_use(
            "Bash", {"command": "x"}, {"stdout": "x"}, session_id="any-cc"
        )
        assert process_hook(json.dumps(payload)) is True

        from one_context.recorder.session import load_session

        assert load_session(sess.session_id).cc_session_id == "any-cc"
    finally:
        abort_session(sess.session_id)
