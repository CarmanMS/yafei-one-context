"""Tests for events.py — stream-json.jsonl → flat event list."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.eval import events as E


def _w(path: Path, lines: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    assert E.parse_stream_json(tmp_path / "nope.jsonl") == []


def test_empty_file_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    p.write_text("", encoding="utf-8")
    assert E.parse_stream_json(p) == []


def test_blank_and_bad_lines_skipped(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    p.write_text(
        '\n   \n{"type":"result","total_cost_usd":0.01,"result":"done"}\n'
        "not-a-json-line\n",
        encoding="utf-8",
    )
    out = E.parse_stream_json(p)
    assert len(out) == 1
    assert out[0]["kind"] == "result"


def test_sys_init_captures_meta(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "system", "subtype": "init",
         "model": "claude-opus-4-7", "cwd": "/tmp/x",
         "tools": ["Read", "Bash", "Write"]},
    ])
    out = E.parse_stream_json(p)
    assert out[0]["kind"] == "sys.init"
    assert out[0]["meta"]["model"] == "claude-opus-4-7"
    assert out[0]["meta"]["tools"] == ["Read", "Bash", "Write"]
    assert "claude-opus-4-7" in out[0]["preview"]


def test_assistant_thinking_text_tool_use(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "I should read the spec.\nThen plan."},
            {"type": "text", "text": "我先看 spec。"},
            {"type": "tool_use", "id": "tu_001", "name": "Read",
             "input": {"file_path": "/x/spec.md"}},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert [e["kind"] for e in out] == ["think", "text", "tool_use"]
    # think: full preserved, preview is one-line
    assert out[0]["full"] == "I should read the spec.\nThen plan."
    assert "\n" not in out[0]["preview"]
    assert out[0]["size"] == len(out[0]["full"])
    # text:
    assert out[1]["full"] == "我先看 spec。"
    # tool_use: input preserved, preview = file_path
    assert out[2]["tool"] == "Read"
    assert out[2]["input"] == {"file_path": "/x/spec.md"}
    assert out[2]["tool_use_id"] == "tu_001"
    assert out[2]["preview"] == "/x/spec.md"


def test_bash_preview_uses_command(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Bash",
             "input": {"command": "ls -la /tmp", "description": "list tmp"}},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert out[0]["preview"] == "ls -la /tmp"
    # full input preserved (Bash content is not stripped)
    assert out[0]["input"]["command"] == "ls -la /tmp"
    assert out[0]["input"]["description"] == "list tmp"


def test_write_content_stripped(tmp_path: Path) -> None:
    """Write.content must be replaced by placeholder (it's in artifacts/)."""
    p = tmp_path / "s.jsonl"
    big = "x" * 9312
    _w(p, [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "tw", "name": "Write",
             "input": {"file_path": "/x/out.md", "content": big}},
        ]}},
    ])
    out = E.parse_stream_json(p)
    inp = out[0]["input"]
    assert inp["file_path"] == "/x/out.md"
    # content placeholder mentions original size
    assert "9312" in inp["content"]
    assert "see artifact" in inp["content"]
    # raw content NOT present anywhere in the event
    flat = json.dumps(out[0], ensure_ascii=False)
    assert big not in flat


def test_edit_content_also_stripped(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    big = "y" * 500
    _w(p, [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "te", "name": "Edit",
             "input": {"file_path": "/x/a.md", "old_string": "a",
                       "new_string": "b", "content": big}},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert "see artifact" in out[0]["input"]["content"]
    assert out[0]["input"]["old_string"] == "a"


def test_tool_result_string_content(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu_001",
             "content": "file contents\nline 2"},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert out[0]["kind"] == "tool_result"
    assert out[0]["full"] == "file contents\nline 2"
    assert out[0]["size"] == 20
    assert out[0]["tool_use_id"] == "tu_001"
    assert out[0]["is_error"] is False
    # preview is one-line
    assert "\n" not in out[0]["preview"]


def test_tool_result_list_content(tmp_path: Path) -> None:
    """Anthropic sometimes returns tool_result.content as a list of blocks."""
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu_002",
             "content": [
                 {"type": "text", "text": "part 1"},
                 {"type": "text", "text": "part 2"},
             ]},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert out[0]["full"] == "part 1part 2"


def test_tool_result_is_error_flag(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu_err",
             "content": "boom", "is_error": True},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert out[0]["is_error"] is True


def test_result_captures_cost(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "result", "total_cost_usd": 1.234, "result": "all done"},
    ])
    out = E.parse_stream_json(p)
    assert out[0]["kind"] == "result"
    assert out[0]["cost_usd"] == 1.234
    assert out[0]["preview"] == "all done"


def test_idx_is_1_based_and_sequential(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "system", "subtype": "init", "model": "m", "cwd": "/", "tools": []},
        {"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "a"},
            {"type": "tool_use", "id": "t", "name": "Read", "input": {"file_path": "/x"}},
        ]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t", "content": "ok"},
        ]}},
    ])
    out = E.parse_stream_json(p)
    assert [e["idx"] for e in out] == [1, 2, 3, 4]


def test_timestamps_propagate_when_t_present(tmp_path: Path) -> None:
    """Stage 2.5.3: provider injects `_t`; events.py surfaces t_ms + t_offset_ms."""
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"_t": 1_700_000_000_000, "type": "system", "subtype": "init",
         "model": "m", "cwd": "/x", "tools": []},
        {"_t": 1_700_000_001_500, "type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "go"},
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/x"}},
        ]}},
        {"_t": 1_700_000_001_900, "type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
        ]}},
        {"_t": 1_700_000_002_700, "type": "result", "total_cost_usd": 0.01, "result": "done"},
    ])
    out = E.parse_stream_json(p)
    # Every event got its t_ms from the line that produced it
    assert [e["t_ms"] for e in out] == [
        1_700_000_000_000, 1_700_000_001_500, 1_700_000_001_500,
        1_700_000_001_900, 1_700_000_002_700,
    ]
    # t_offset_ms is relative to first event
    assert [e["t_offset_ms"] for e in out] == [0, 1500, 1500, 1900, 2700]


def test_timestamps_absent_yields_none(tmp_path: Path) -> None:
    """Old providers without `_t` produce events with t_ms=None / t_offset_ms=None."""
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "system", "subtype": "init", "model": "m", "cwd": "/", "tools": []},
        {"type": "result", "total_cost_usd": 0.01, "result": "done"},
    ])
    out = E.parse_stream_json(p)
    assert all(e["t_ms"] is None for e in out)
    assert all(e["t_offset_ms"] is None for e in out)


def test_mixed_timestamped_lines(tmp_path: Path) -> None:
    """Some lines have _t, others don't (e.g., partial provider upgrade)."""
    p = tmp_path / "s.jsonl"
    _w(p, [
        {"type": "system", "subtype": "init", "model": "m", "cwd": "/", "tools": []},  # no _t
        {"_t": 1_700_000_005_000, "type": "result", "total_cost_usd": 0.01, "result": "done"},
    ])
    out = E.parse_stream_json(p)
    # first event has no t_ms, but base_t comes from the second event
    assert out[0]["t_ms"] is None
    assert out[1]["t_ms"] == 1_700_000_005_000
    # first event has None offset; second is anchor
    assert out[0]["t_offset_ms"] is None
    assert out[1]["t_offset_ms"] == 0


def test_real_stream_json_from_phase1_run() -> None:
    """End-to-end against the real Phase 1 run committed to the repo."""
    repo = Path(__file__).resolve().parents[4]
    stream = (repo / "skills/cover-prompt/evals/mid-video"
                   / "__reports/1780104720-b24798/stream-json.jsonl")
    if not stream.is_file():
        pytest.skip(f"real stream-json missing: {stream}")
    events = E.parse_stream_json(stream)
    # Phase 1 run has 41 events
    assert len(events) == 41
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "sys.init"
    assert kinds[-1] == "result"
    assert kinds.count("think") == 4
    assert kinds.count("text") == 3
    assert kinds.count("tool_use") == 16
    assert kinds.count("tool_result") == 16
    # The Write step input has content stripped
    write_evts = [e for e in events if e.get("tool") == "Write"]
    assert len(write_evts) == 1
    assert "see artifact" in write_evts[0]["input"]["content"]
