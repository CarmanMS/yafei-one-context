"""judge_skill_call mock 单测 + judge_with_retry 重试单测。

真接 claude -p 测试在 M2.2 slow（默认 skip）。
"""
import json
from unittest.mock import patch

import pytest

from one_context.usage_eval.judge import judge_skill_call, JudgeResult


def _full_dim_json(score=0.82, verdict="good"):
    return json.dumps({
        "per_dimension": {
            "dim_match":        {"score": score, "reason": "ok"},
            "dim_path":         {"score": score, "reason": "ok"},
            "dim_completeness": {"score": score, "reason": "ok"},
            "dim_correction":   {"score": score, "reason": "ok"},
            "dim_satisfaction": {"score": score, "reason": "ok"},
        },
        "score": score,
        "verdict": verdict,
        "reason": "总评",
        "suggested_patch_md": "## 建议 1\n```diff\n- a\n+ b\n```\n",
    })


def test_judge_skill_call_parses_json_output():
    with patch("one_context.usage_eval.judge._spawn_judge_llm", return_value=_full_dim_json(0.9, "good")):
        r = judge_skill_call(skill_md="x", rubric_md="r", slot_summary="s", surrounding="ctx")
    assert isinstance(r, JudgeResult)
    assert r.score == 0.9
    assert r.verdict == "good"
    assert r.per_dimension["dim_match"].score == 0.9
    assert "建议 1" in r.suggested_patch_md


def test_judge_skill_call_handles_extra_prose_around_json():
    fake = 'Here is my evaluation:\n```json\n' + _full_dim_json(0.5, "needs-work") + '\n```\nDone.'
    with patch("one_context.usage_eval.judge._spawn_judge_llm", return_value=fake):
        r = judge_skill_call(skill_md="x", rubric_md="r", slot_summary="s", surrounding="ctx")
    assert r.score == 0.5
    assert r.verdict == "needs-work"


def test_judge_skill_call_invalid_json_raises():
    with patch("one_context.usage_eval.judge._spawn_judge_llm", return_value="not json at all"):
        with pytest.raises(ValueError, match="no JSON object"):
            judge_skill_call(skill_md="x", rubric_md="r", slot_summary="s", surrounding="ctx")


def test_judge_with_retry_success_after_two_failures():
    from one_context.usage_eval.judge import judge_with_retry
    ok = _full_dim_json(0.9, "good")
    seq = iter([RuntimeError("net"), RuntimeError("net"), ok])

    def side(**kw):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    with patch("one_context.usage_eval.judge._spawn_judge_llm", side_effect=side), \
         patch("one_context.usage_eval.judge.time.sleep"):
        r = judge_with_retry(skill_md="x", rubric_md="r", slot_summary="s", surrounding="c")
    assert r.score == 0.9


def test_judge_with_retry_exhausted_raises():
    from one_context.usage_eval.judge import judge_with_retry
    with patch("one_context.usage_eval.judge._spawn_judge_llm",
               side_effect=RuntimeError("persistent")), \
         patch("one_context.usage_eval.judge.time.sleep"):
        with pytest.raises(RuntimeError, match="judge failed after"):
            judge_with_retry(skill_md="x", rubric_md="r", slot_summary="s", surrounding="c")
