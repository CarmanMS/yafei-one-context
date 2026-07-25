"""evaluate_session 端到端集成测（LLM 全 mock）。

覆盖：
- payload 主路径（M-FIX-2 transcript_path 直接用）
- macOS resolve 不匹配陷阱（评审 D-03）
- S-02 错误兜底：judge 失败也要写 report.md status: error
"""
import json
from pathlib import Path
from unittest.mock import patch

from one_context.usage_eval.orchestrator import evaluate_session


_FAKE_JUDGE_JSON = json.dumps({
    "per_dimension": {
        "dim_match":        {"score": 0.8, "reason": "ok"},
        "dim_path":         {"score": 0.8, "reason": "ok"},
        "dim_completeness": {"score": 0.8, "reason": "ok"},
        "dim_correction":   {"score": 0.8, "reason": "ok"},
        "dim_satisfaction": {"score": 0.8, "reason": "ok"},
    },
    "score": 0.8, "verdict": "good", "reason": "r", "suggested_patch_md": "",
})


def _make_repo_with_jsonl(tmp_path, sid="abcd1234"):
    """构造 fake repo + skill + jsonl，返回 (repo_root, home, payload)。

    评审 D-03：jsonl 路径必须用 repo.resolve()，否则 macOS /var/folders/
    会被 jsonl_path 内部 resolve 成 /private/var/folders/ 而对不上。
    """
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "cover-prompt"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# cover-prompt\n\nDo X.\n")

    home = tmp_path / "home"
    # 直接给 transcript_path（M-FIX-2 主路径）
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        '{"type":"user","message":{"content":"hi"}}\n'
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1",'
        '"name":"Skill","input":{"skill":"cover-prompt"}}]}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1",'
        '"content":"done"}]}}\n'
    )
    payload = {
        "session_id": sid,
        "transcript_path": str(transcript),
        "cwd": str(repo.resolve()),
        "hook_event_name": "SessionEnd",
        "reason": "prompt_input_exit",
    }
    return repo, home, payload


def test_evaluate_session_end_to_end_with_mock_payload(tmp_path):
    """M-FIX-2 主路径：用 payload + transcript_path 跑通全链路"""
    repo, home, payload = _make_repo_with_jsonl(tmp_path)
    skill_dir = repo / "skills" / "cover-prompt"

    fake_rubric = "---\nskill: cover-prompt\nskill_md_sha256: STUB\n---\n# r\n"
    with patch("one_context.usage_eval.rubric._spawn_rubric_llm", return_value=fake_rubric), \
         patch("one_context.usage_eval.judge._spawn_judge_llm", return_value=_FAKE_JUDGE_JSON):
        results = evaluate_session(repo_root=repo, payload=payload, home=home)

    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["score"] == 0.8
    eval_dir = skill_dir / "__usage_eval"
    assert (eval_dir / "RUBRIC.md").exists()
    assert (eval_dir / "INDEX.md").exists()
    runs = [p for p in eval_dir.iterdir() if p.is_dir() and p.name[0].isdigit()]
    assert len(runs) == 1
    assert (runs[0] / "report.md").exists()
    assert (runs[0] / "suggested_patch.md").exists()
    assert (runs[0] / "slot.json").exists()
    # INDEX 行格式正确
    idx_line = (eval_dir / "INDEX.md").read_text().strip()
    assert "status=ok" in idx_line


def test_evaluate_session_writes_error_status_when_judge_fails(tmp_path):
    """评审 S-02：judge 3 次重试全失败 → 仍写 report.md status: error"""
    repo, home, payload = _make_repo_with_jsonl(tmp_path)
    skill_dir = repo / "skills" / "cover-prompt"

    fake_rubric = "---\nskill: cover-prompt\nskill_md_sha256: STUB\n---\n# r\n"
    with patch("one_context.usage_eval.rubric._spawn_rubric_llm", return_value=fake_rubric), \
         patch("one_context.usage_eval.judge._spawn_judge_llm",
               side_effect=RuntimeError("persistent")), \
         patch("one_context.usage_eval.judge.time.sleep"):  # 跳过 1+4+16s 等待
        results = evaluate_session(repo_root=repo, payload=payload, home=home)

    assert len(results) == 1
    assert results[0]["status"] == "error"
    eval_dir = skill_dir / "__usage_eval"
    runs = [p for p in eval_dir.iterdir() if p.is_dir() and p.name[0].isdigit()]
    fm = (runs[0] / "report.md").read_text()
    assert "status: error" in fm
    assert "verdict: error" in fm
    assert "RuntimeError" in fm  # error_message 含 exception 类型
    # INDEX 行也应记 status=error
    assert "status=error" in (eval_dir / "INDEX.md").read_text()


def test_evaluate_session_skips_non_repo_skill(tmp_path):
    """skills/<name>/SKILL.md 不存在的 skill 直接跳过"""
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    # 故意不建 skills/foo/

    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1",'
        '"name":"Skill","input":{"skill":"foo"}}]}}\n'
    )
    payload = {
        "session_id": "sid",
        "transcript_path": str(transcript),
        "cwd": str(repo.resolve()),
        "hook_event_name": "SessionEnd",
    }
    results = evaluate_session(repo_root=repo, payload=payload, home=tmp_path / "h")
    assert results == []


def test_evaluate_session_requires_payload_or_sid(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="either"):
        evaluate_session(repo_root=tmp_path)
