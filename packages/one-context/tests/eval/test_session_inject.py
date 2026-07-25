"""MockRound schema + load_mock_rounds tests (ISS-024 / Stage 2.7.A.2).

Cover the loader contract before Stage 2.7.B (SessionFileInjector) needs it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from one_context.eval.session_inject import (
    MAX_SESSION_FILE_BYTES,
    MAX_TOOL_RESULT_BYTES,
    MockRound,
    SessionFileInjector,
    _project_hash,
    detect_cc_version,
    load_mock_rounds,
    session_file_path,
)


# ── MockRound schema ───────────────────────────────────────────────────────


def test_mock_round_minimum_fields() -> None:
    """Required: round_id / tool_name / tool_result. Others have defaults."""
    mr = MockRound(
        round_id="r1",
        tool_name="WebFetch",
        tool_result="ok",
    )
    assert mr.round_id == "r1"
    assert mr.tool_name == "WebFetch"
    assert mr.tool_result == "ok"
    assert mr.tool_input == {}
    assert mr.assistant_thinking == ""
    assert mr.boundary_type == "local_tool"


def test_mock_round_tool_result_can_be_dict_or_list() -> None:
    """tool_result accepts str / dict / list — injector serializes on write."""
    mr_dict = MockRound(round_id="r1", tool_name="WebFetch",
                        tool_result={"title": "x", "score": 999})
    assert mr_dict.tool_result["score"] == 999

    mr_list = MockRound(round_id="r2", tool_name="WebFetch",
                        tool_result=[{"id": 1}, {"id": 2}])
    assert len(mr_list.tool_result) == 2


def test_mock_round_empty_round_id_rejected() -> None:
    with pytest.raises(Exception) as exc:
        MockRound(round_id="", tool_name="WebFetch", tool_result="ok")
    assert "round_id" in str(exc.value).lower()


def test_mock_round_oversize_tool_result_rejected() -> None:
    """Per-round cap stops authors from accidentally inlining huge payloads."""
    huge = "x" * (MAX_TOOL_RESULT_BYTES + 1)
    with pytest.raises(Exception) as exc:
        MockRound(round_id="r1", tool_name="WebFetch", tool_result=huge)
    assert "tool_result" in str(exc.value).lower()


def test_mock_round_extra_field_rejected() -> None:
    with pytest.raises(Exception) as exc:
        MockRound(
            round_id="r1",
            tool_name="WebFetch",
            tool_result="ok",
            unknown_field="hello",
        )
    assert "unknown_field" in str(exc.value) or "extra" in str(exc.value).lower()


# ── load_mock_rounds loader ────────────────────────────────────────────────


def _write_round(dir_path: Path, name: str, body: str) -> Path:
    p = dir_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_load_mock_rounds_lexical_order(tmp_path: Path) -> None:
    """Files load in lexical filename order — author controls round sequence
    via numeric prefix convention like `round-01-...`, `round-02-...`."""
    d = tmp_path / "mock_rounds"
    d.mkdir()
    _write_round(d, "round-02-blog.yaml",
                 "round_id: r2\ntool_name: WebFetch\ntool_result: 'blog ok'\n")
    _write_round(d, "round-01-hn.yaml",
                 "round_id: r1\ntool_name: WebFetch\ntool_result: 'hn ok'\n")
    _write_round(d, "round-03-rss.yaml",
                 "round_id: r3\ntool_name: WebFetch\ntool_result: 'rss ok'\n")

    rounds = load_mock_rounds(d)
    assert [r.round_id for r in rounds] == ["r1", "r2", "r3"]


def test_load_mock_rounds_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc:
        load_mock_rounds(tmp_path / "does-not-exist")
    assert "mock_rounds_dir" in str(exc.value).lower()


def test_load_mock_rounds_skips_non_yaml(tmp_path: Path) -> None:
    """README / other files in the directory are ignored gracefully."""
    d = tmp_path / "mock_rounds"
    d.mkdir()
    _write_round(d, "round-01.yaml",
                 "round_id: r1\ntool_name: Bash\ntool_result: 'ok'\n")
    _write_round(d, "README.md", "# notes about these mocks\n")
    _write_round(d, "round-02.yml",  # .yml also accepted
                 "round_id: r2\ntool_name: Bash\ntool_result: 'ok2'\n")

    rounds = load_mock_rounds(d)
    assert [r.round_id for r in rounds] == ["r1", "r2"]


def test_load_mock_rounds_duplicate_round_id_rejected(tmp_path: Path) -> None:
    """round_id must be unique within a directory — baseline digest keys on it."""
    d = tmp_path / "mock_rounds"
    d.mkdir()
    _write_round(d, "round-01.yaml",
                 "round_id: same\ntool_name: Bash\ntool_result: 'a'\n")
    _write_round(d, "round-02.yaml",
                 "round_id: same\ntool_name: Bash\ntool_result: 'b'\n")

    with pytest.raises(ValueError) as exc:
        load_mock_rounds(d)
    msg = str(exc.value)
    assert "duplicate" in msg.lower() and "same" in msg


def test_load_mock_rounds_invalid_yaml_rejected(tmp_path: Path) -> None:
    d = tmp_path / "mock_rounds"
    d.mkdir()
    _write_round(d, "round-01.yaml", "round_id: r1\n  bad: indentation:\n")
    with pytest.raises(ValueError) as exc:
        load_mock_rounds(d)
    assert "invalid yaml" in str(exc.value).lower() or "yaml" in str(exc.value).lower()


def test_load_mock_rounds_schema_violation_rejected(tmp_path: Path) -> None:
    """File parses as YAML but violates MockRound schema (missing tool_name)."""
    d = tmp_path / "mock_rounds"
    d.mkdir()
    _write_round(d, "round-01.yaml",
                 "round_id: r1\ntool_result: 'ok'\n")  # tool_name missing
    with pytest.raises(ValueError) as exc:
        load_mock_rounds(d)
    assert "schema validation" in str(exc.value).lower()


# ── SessionFileInjector (Stage 2.7.B) ──────────────────────────────────────


import json
import os
from unittest.mock import patch


def _read_jsonl(path: Path) -> list[dict]:
    """Read a jsonl file as a list of dicts. Test helper."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_injector(
    monkeypatch,
    sandbox_root: Path,
    cc_version: str = "2.1.156",
    model: str = "claude-opus-4-7",
) -> SessionFileInjector:
    """Build an injector whose ~/.claude path lives under tmp_path.

    Tests must NOT touch the real ~/.claude/projects/. Each test redirects
    HOME (and therefore Path.home()) via monkeypatch.
    """
    fake_home = sandbox_root.parent / "fake-home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    return SessionFileInjector(
        sandbox_root=sandbox_root,
        cc_version=cc_version,
        requested_model=model,
    )


def test_project_hash_uses_realpath(tmp_path: Path) -> None:
    """macOS pitfall: cc uses realpath for the project hash, not the
    user-facing cwd. A symlink → /private/tmp → must be resolved."""
    real_dir = tmp_path / "real-sandbox"
    real_dir.mkdir()
    link_dir = tmp_path / "link-sandbox"
    link_dir.symlink_to(real_dir)

    h_real = _project_hash(real_dir)
    h_link = _project_hash(link_dir)

    # Both resolve to the same hash because realpath flattens the symlink.
    assert h_real == h_link
    # And the hash contains the real path, not the symlink path.
    assert "real-sandbox" in h_real
    assert "link-sandbox" not in h_real


def test_session_file_path_layout(tmp_path: Path) -> None:
    """Filename MUST be `<session_id>.jsonl` verbatim — cc resolves --resume
    by scanning the project-hash dir for this exact filename, so any other
    naming surfaces as "No conversation found with session ID: ..." at
    spawn time (Stage 2.7.G real-run validation caught this)."""
    p = session_file_path(tmp_path / "sbx", "d880d7a9-d722-45a5-b68e-8fb4b086be4c")
    assert p.name == "d880d7a9-d722-45a5-b68e-8fb4b086be4c.jsonl"
    assert p.parent.name.startswith("-")  # project hash format


def test_injector_single_round_writes_3_messages(tmp_path: Path, monkeypatch) -> None:
    """1 user (query) + 1 assistant(tool_use) + 1 user(tool_result) = 3 lines."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)

    rounds = [MockRound(
        round_id="r1",
        tool_name="WebFetch",
        tool_input={"url": "https://example.com"},
        tool_result="<title>OK</title>",
        assistant_thinking="I'll fetch the page.",
    )]
    session_id = injector.create_session_with_mock_history(
        user_input="please fetch example.com title",
        mock_rounds=rounds,
        run_id="rid-001",
    )

    path = injector.session_dir / f"{session_id}.jsonl"
    assert path.is_file()
    msgs = _read_jsonl(path)
    assert len(msgs) == 3
    types = [m["type"] for m in msgs]
    assert types == ["user", "assistant", "user"]

    # Session ID is propagated everywhere AND returned to caller.
    assert all(m["sessionId"] == session_id for m in msgs)


def test_injector_multi_round_writes_1_plus_2N(tmp_path: Path, monkeypatch) -> None:
    """N rounds → 1 initial user + N × (assistant + tool_result) = 1 + 2N lines."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)
    rounds = [
        MockRound(round_id=f"r{i}", tool_name="WebFetch", tool_result=f"result-{i}")
        for i in range(3)
    ]
    sid = injector.create_session_with_mock_history(
        user_input="multi-step query",
        mock_rounds=rounds,
        run_id="rid-multi",
    )

    path = injector.session_dir / f"{sid}.jsonl"
    msgs = _read_jsonl(path)
    assert len(msgs) == 1 + 2 * 3
    # type sequence: user, assistant, user, assistant, user, assistant, user
    expected = ["user"] + ["assistant", "user"] * 3
    assert [m["type"] for m in msgs] == expected


def test_injector_parent_uuid_chain(tmp_path: Path, monkeypatch) -> None:
    """Each message's parentUuid links to the prior message's uuid.

    cc's resume logic uses this chain to reconstruct conversation order;
    a broken chain would surface as cc dropping or reordering history.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)
    rounds = [
        MockRound(round_id="r1", tool_name="Bash", tool_result="ok-1"),
        MockRound(round_id="r2", tool_name="Bash", tool_result="ok-2"),
    ]
    sid = injector.create_session_with_mock_history(
        user_input="q",
        mock_rounds=rounds,
        run_id="rid-chain",
    )

    msgs = _read_jsonl(injector.session_dir / f"{sid}.jsonl")
    # First message has no parent.
    assert msgs[0]["parentUuid"] is None
    # Every other message's parentUuid == previous message's uuid.
    for i in range(1, len(msgs)):
        assert msgs[i]["parentUuid"] == msgs[i - 1]["uuid"]


def test_injector_tool_use_id_pairs_with_tool_result(tmp_path: Path, monkeypatch) -> None:
    """The assistant(tool_use).id MUST match the user(tool_result).tool_use_id.

    If they don't match cc treats the result as belonging to no tool call
    and prefill semantics break — the LLM may end up re-invoking the
    "missing" tool, defeating the whole mock."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)
    rounds = [MockRound(round_id="r1", tool_name="WebFetch", tool_result="ok")]
    sid = injector.create_session_with_mock_history(
        user_input="q", mock_rounds=rounds, run_id="rid-pair",
    )

    msgs = _read_jsonl(injector.session_dir / f"{sid}.jsonl")
    assistant_msg = msgs[1]
    tool_result_msg = msgs[2]
    asst_tool_use_id = next(
        b["id"] for b in assistant_msg["message"]["content"] if b["type"] == "tool_use"
    )
    tr_tool_use_id = tool_result_msg["message"]["content"][0]["tool_use_id"]
    assert asst_tool_use_id == tr_tool_use_id

    # Also: sourceToolAssistantUUID points to the assistant uuid.
    assert tool_result_msg["sourceToolAssistantUUID"] == assistant_msg["uuid"]


def test_injector_model_and_version_propagated(tmp_path: Path, monkeypatch) -> None:
    """requested_model goes into assistant.message.model; cc_version into
    every message's `version`. Both must be configurable so the runner can
    pin to whatever the live cc + scenario expect."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(
        monkeypatch, sandbox,
        cc_version="2.1.999",
        model="claude-opus-9-9",
    )
    rounds = [MockRound(round_id="r1", tool_name="Bash", tool_result="ok")]
    sid = injector.create_session_with_mock_history(
        user_input="q", mock_rounds=rounds, run_id="rid-meta",
    )

    msgs = _read_jsonl(injector.session_dir / f"{sid}.jsonl")
    assert all(m["version"] == "2.1.999" for m in msgs)
    assistant_msg = msgs[1]
    assert assistant_msg["message"]["model"] == "claude-opus-9-9"


def test_injector_tool_result_serialization(tmp_path: Path, monkeypatch) -> None:
    """str → kept as-is. dict/list → JSON-stringified (cc tool_result.content
    is always a string in the on-disk schema)."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)
    rounds = [
        MockRound(round_id="r-str", tool_name="Bash", tool_result="plain string"),
        MockRound(round_id="r-dict", tool_name="Bash",
                  tool_result={"key": "value", "n": 42}),
        MockRound(round_id="r-list", tool_name="Bash",
                  tool_result=[1, 2, 3]),
    ]
    sid = injector.create_session_with_mock_history(
        user_input="q", mock_rounds=rounds, run_id="rid-types",
    )

    msgs = _read_jsonl(injector.session_dir / f"{sid}.jsonl")
    # tool_result messages are at indices 2, 4, 6
    assert msgs[2]["message"]["content"][0]["content"] == "plain string"
    assert msgs[4]["message"]["content"][0]["content"] == '{"key": "value", "n": 42}'
    assert msgs[6]["message"]["content"][0]["content"] == "[1, 2, 3]"


def test_injector_cumulative_size_cap(tmp_path: Path, monkeypatch) -> None:
    """Cumulative tool_result size > MAX_SESSION_FILE_BYTES → fail-fast,
    no file written. Per-round cap was checked at MockRound time; this
    catches the additive case (many small rounds adding up)."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)
    # Six rounds × ~900KB each ≈ 5.4MB > 5MB cap
    big = "x" * (900_000)
    rounds = [
        MockRound(round_id=f"r{i}", tool_name="Bash", tool_result=big)
        for i in range(6)
    ]
    with pytest.raises(ValueError) as exc:
        injector.create_session_with_mock_history(
            user_input="q", mock_rounds=rounds, run_id="rid-big",
        )
    assert "cumulative" in str(exc.value).lower()
    # No file should have been written on failure.
    # No file should have been written under ANY session id (cap is pre-flight).
    # The session_dir might exist but must not contain forged jsonl files.
    if injector.session_dir.exists():
        assert not any(injector.session_dir.glob("*.jsonl"))


def test_injector_required_schema_fields_present(tmp_path: Path, monkeypatch) -> None:
    """Spot-check that the cc 2.1.156 must-have fields are all written.

    See session-injection-spike-result.md §4 for the exhaustive table.
    If cc ever stops accepting these we want this test to surface it.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    injector = _make_injector(monkeypatch, sandbox)
    rounds = [MockRound(
        round_id="r1", tool_name="WebFetch",
        tool_input={"url": "https://x"}, tool_result="ok",
        assistant_thinking="thinking",
    )]
    sid = injector.create_session_with_mock_history(
        user_input="q", mock_rounds=rounds, run_id="rid-schema",
    )

    msgs = _read_jsonl(injector.session_dir / f"{sid}.jsonl")

    # All messages share these base fields
    for m in msgs:
        for k in ("isSidechain", "userType", "entrypoint", "cwd", "sessionId",
                  "version", "gitBranch", "uuid", "timestamp", "type"):
            assert k in m, f"missing base field {k} on msg type={m.get('type')}"
        assert m["entrypoint"] == "sdk-cli"
        assert m["gitBranch"] == "HEAD"

    # user (text) first
    assert msgs[0]["permissionMode"] == "bypassPermissions"
    assert "promptId" in msgs[0]

    # assistant (tool_use)
    asst = msgs[1]
    assert asst["message"]["stop_reason"] == "tool_use"
    assert "usage" in asst["message"]
    tool_use_blocks = [b for b in asst["message"]["content"] if b["type"] == "tool_use"]
    assert len(tool_use_blocks) == 1

    # user (tool_result)
    tr = msgs[2]
    assert "toolUseResult" in tr
    assert "sourceToolAssistantUUID" in tr
    assert "promptId" in tr
    assert tr["message"]["content"][0]["is_error"] is False


# ── detect_cc_version ──────────────────────────────────────────────────────


class _FakeCompleted:
    def __init__(self, stdout="", stderr=""):
        self.stdout = stdout
        self.stderr = stderr


def test_detect_cc_version_parses_normal_output() -> None:
    detect_cc_version.cache_clear()
    with patch("subprocess.run", return_value=_FakeCompleted(stdout="2.1.156 (Claude Code)\n")):
        assert detect_cc_version() == "2.1.156"


def test_detect_cc_version_falls_back_when_cc_missing() -> None:
    detect_cc_version.cache_clear()
    with patch("subprocess.run", side_effect=FileNotFoundError("claude not on PATH")):
        assert detect_cc_version() == "unknown"


def test_detect_cc_version_cached_across_calls() -> None:
    """lru_cache means only the first call actually spawns claude."""
    detect_cc_version.cache_clear()
    with patch("subprocess.run", return_value=_FakeCompleted(stdout="3.0.0\n")) as m:
        v1 = detect_cc_version()
        v2 = detect_cc_version()
        v3 = detect_cc_version()
    assert v1 == v2 == v3 == "3.0.0"
    assert m.call_count == 1
