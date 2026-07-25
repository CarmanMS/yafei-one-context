from pathlib import Path

import pytest

from one_context.usage_eval.session_parser import (
    jsonl_path,
    jsonl_from_payload,
    parse_skill_slots,
    surrounding_turns,
    SkillSlot,
)


def test_jsonl_path_replaces_slash_with_dash():
    cwd = Path("/Users/superno/Documents/code/creative/one-context")
    sid = "3a9f8b21-1234-5678-9abc-def012345678"
    home = Path("/Users/superno")
    expected = home / ".claude/projects/-Users-superno-Documents-code-creative-one-context" / f"{sid}.jsonl"
    assert jsonl_path(cwd, sid, home=home) == expected


def test_jsonl_path_handles_trailing_slash(tmp_path):
    # 用 tmp_path 验证 resolve 行为（trailing slash 通常被 resolve 吃掉）
    base = tmp_path / "foo" / "bar"
    base.mkdir(parents=True)
    cwd = Path(str(base) + "/")  # 显式带 trailing slash
    home = Path("/h")
    out = jsonl_path(cwd, "abc", home=home)
    # 期望：resolved 后不带 trailing slash，路径里 / 全部变 -
    assert out == Path(f"/h/.claude/projects/{str(base.resolve()).replace('/', '-')}/abc.jsonl")


def test_jsonl_from_payload_uses_transcript_path():
    """M-FIX-2：优先用 hook stdin 给的 transcript_path"""
    payload = {
        "session_id": "7b40e98e-fb0b-4fb2-91ec-7d3036e7c865",
        "transcript_path": "/Users/superno/.claude/projects/-Users-superno-Documents-code-creative-one-context/7b40e98e-fb0b-4fb2-91ec-7d3036e7c865.jsonl",
        "cwd": "/Users/superno/Documents/code/creative/one-context",
        "hook_event_name": "SessionEnd",
        "reason": "prompt_input_exit",
    }
    p = jsonl_from_payload(payload)
    assert p == Path(payload["transcript_path"])


def test_jsonl_from_payload_falls_back_to_reverse_lookup(tmp_path):
    """transcript_path 缺失（cc 升级 schema）时回退到 cwd 反推算法"""
    real_cwd = tmp_path / "foo" / "bar"
    real_cwd.mkdir(parents=True)
    payload = {
        "session_id": "abc",
        "cwd": str(real_cwd),
        "hook_event_name": "SessionEnd",
    }
    home = tmp_path / "home"
    expected = home / ".claude/projects" / str(real_cwd.resolve()).replace("/", "-") / "abc.jsonl"
    assert jsonl_from_payload(payload, home=home) == expected


def test_jsonl_from_payload_raises_when_no_sid_and_no_path():
    with pytest.raises(ValueError, match="missing"):
        jsonl_from_payload({"hook_event_name": "SessionEnd"})


# ─── parse_skill_slots ────────────────────────────────────────────


def test_parse_skill_slots_extracts_skill_tool_uses():
    """fixture 含 2 个 Skill tool_use + 配对 result + 1 损坏行"""
    fixture = Path(__file__).parent / "fixtures" / "sample-session.jsonl"
    slots = parse_skill_slots(fixture)
    # 2 Skill 调用，两个都不含 ':'，都应被抽出
    assert len(slots) == 2
    s0 = slots[0]
    assert isinstance(s0, SkillSlot)
    assert s0.skill_name == "discover"
    assert s0.slot_idx == 0
    assert s0.tool_use_id.startswith("fc-")
    assert s0.tool_result is not None  # 配对 result 必须命中
    s1 = slots[1]
    assert s1.skill_name == "using-superpowers"
    assert s1.slot_idx == 1


def test_parse_skill_slots_returns_empty_for_no_skill_session(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text('{"type":"user","message":{"content":"hi"}}\n')
    assert parse_skill_slots(f) == []


def test_parse_skill_slots_skips_corrupted_lines(tmp_path, caplog):
    import logging
    caplog.set_level(logging.WARNING)
    f = tmp_path / "mixed.jsonl"
    f.write_text(
        '{"type":"user","message":{"content":"hi"}}\n'
        'NOT JSON THIS LINE\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","id":"x","input":{"skill":"foo"}}]}}\n'
    )
    slots = parse_skill_slots(f)
    assert len(slots) == 1
    assert "malformed" in caplog.text.lower() or "skipping" in caplog.text.lower()


def test_parse_skill_slots_skips_plugin_skills(tmp_path):
    """M-FIX-5：带 ':' 的 plugin skill 不在仓内 skills/，跳过"""
    f = tmp_path / "plugin.jsonl"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","id":"p1",'
        '"input":{"skill":"superpowers:executing-plans","args":"x"}}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","id":"r1",'
        '"input":{"skill":"info-radar"}}]}}\n'
    )
    slots = parse_skill_slots(f)
    assert len(slots) == 1
    assert slots[0].skill_name == "info-radar"


def test_parse_skill_slots_warns_on_missing_input_skill(tmp_path, caplog):
    """M-FIX-4：缺 input.skill = cc schema 变化信号，warn + skip"""
    import logging
    caplog.set_level(logging.WARNING)
    f = tmp_path / "broken.jsonl"
    f.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","id":"b1",'
        '"input":{"name":"misnamed_field"}}]}}\n'
    )
    slots = parse_skill_slots(f)
    assert slots == []
    txt = caplog.text.lower()
    assert "missing input.skill" in txt or "schema may have changed" in txt


def test_parse_skill_slots_returns_empty_for_nonexistent_file(tmp_path, caplog):
    slots = parse_skill_slots(tmp_path / "nope.jsonl")
    assert slots == []
    assert "not found" in caplog.text.lower()


# ─── surrounding_turns ────────────────────────────────────────────


def test_surrounding_turns_returns_n_before_and_after(tmp_path):
    """7 条 turn，target 在第 4 行，n=2 → 返回 line 2,3,5,6（不含 target）"""
    f = tmp_path / "s.jsonl"
    f.write_text("\n".join(
        f'{{"type":"user","message":{{"content":"u{i}"}}}}'
        for i in range(1, 8)
    ) + "\n")
    ctx = surrounding_turns(f, target_line=4, n=2)
    assert len(ctx) == 4  # 2 before + 2 after, target excluded
    assert "u2" in ctx[0]["content_snippet"]
    assert ctx[0]["line"] == 2
    assert "u3" in ctx[1]["content_snippet"]
    assert "u5" in ctx[2]["content_snippet"]
    assert "u6" in ctx[-1]["content_snippet"]


def test_surrounding_turns_truncates_long_content(tmp_path):
    """content > 200 char 应被截断 + 加 '...' 标记"""
    f = tmp_path / "long.jsonl"
    long_content = "x" * 500
    f.write_text(
        f'{{"type":"user","message":{{"content":"{long_content}"}}}}\n'
        f'{{"type":"user","message":{{"content":"target"}}}}\n'
    )
    ctx = surrounding_turns(f, target_line=2, n=2)
    assert len(ctx) == 1
    snippet = ctx[0]["content_snippet"]
    assert snippet.endswith("...")
    assert len(snippet) <= 210  # 200 + "..."


def test_surrounding_turns_handles_edges(tmp_path):
    """target 在边界（line=1）时只返回 after；target 超出文件时返回空"""
    f = tmp_path / "tiny.jsonl"
    f.write_text(
        '{"type":"user","message":{"content":"u1"}}\n'
        '{"type":"user","message":{"content":"u2"}}\n'
        '{"type":"user","message":{"content":"u3"}}\n'
    )
    # target=1 → 前 0 + 后 2
    ctx = surrounding_turns(f, target_line=1, n=2)
    assert len(ctx) == 2
    assert "u2" in ctx[0]["content_snippet"]
    # target 超出
    assert surrounding_turns(f, target_line=100, n=2) == []


def test_surrounding_turns_skips_corrupted_lines(tmp_path):
    """中间损坏行不该污染上下文窗口"""
    f = tmp_path / "mix.jsonl"
    f.write_text(
        '{"type":"user","message":{"content":"a"}}\n'
        'BROKEN\n'
        '{"type":"user","message":{"content":"target"}}\n'
        '{"type":"user","message":{"content":"b"}}\n'
    )
    ctx = surrounding_turns(f, target_line=3, n=2)
    # 只能拿到 line 1 (a) + line 4 (b)；BROKEN 跳过
    assert len(ctx) == 2
    contents = [c["content_snippet"] for c in ctx]
    assert any("a" in c for c in contents)
    assert any("b" in c for c in contents)


def test_surrounding_turns_returns_empty_for_missing_file(tmp_path):
    assert surrounding_turns(tmp_path / "nope.jsonl", target_line=1, n=2) == []
