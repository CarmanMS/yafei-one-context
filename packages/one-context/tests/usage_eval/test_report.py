"""report 渲染 + atomic INDEX append 测试。

并发原子性测用 multiprocessing.Process（评审 S-04：fcntl.flock 是 per-process
锁，线程级测不出真原子性）。
"""
import multiprocessing as mp
from pathlib import Path

from one_context.usage_eval.report import (
    RunArtifacts,
    atomic_append_index,
    index_line,
    write_run_artifacts,
)
from one_context.usage_eval.judge import DimScore, JudgeResult


def _judge_stub(score=0.82, verdict="good"):
    dims = {
        k: DimScore(score=score, reason="ok")
        for k in ("dim_match", "dim_path", "dim_completeness", "dim_correction", "dim_satisfaction")
    }
    return JudgeResult(
        per_dimension=dims, score=score, verdict=verdict,
        reason="r", suggested_patch_md="## p\n",
    )


def test_write_run_artifacts_creates_files(tmp_path):
    skill_dir = tmp_path / "cover-prompt"
    (skill_dir / "__usage_eval").mkdir(parents=True)
    art = RunArtifacts(
        skill_dir=skill_dir, skill_name="cover-prompt",
        run_id="1748940000-3a9f8b21-007", sid="3a9f8b21",
        slot_idx=7, judge=_judge_stub(),
        slot_payload={"skill": "cover-prompt", "input": {}, "result": ""},
        rubric_sha="abc",
    )
    out_dir = write_run_artifacts(art)
    assert (out_dir / "report.md").exists()
    assert (out_dir / "suggested_patch.md").exists()
    assert (out_dir / "slot.json").exists()
    fm = (out_dir / "report.md").read_text()
    assert "score: 0.82" in fm
    assert "verdict: good" in fm
    assert "status: ok" in fm


def test_write_run_artifacts_error_status(tmp_path):
    """评审 S-02：judge 失败也要落完整产物，status: error + error_message"""
    skill_dir = tmp_path / "broken"
    (skill_dir / "__usage_eval").mkdir(parents=True)
    art = RunArtifacts(
        skill_dir=skill_dir, skill_name="broken",
        run_id="1748940000-3a9f8b21-009", sid="3a9f8b21",
        slot_idx=9, judge=_judge_stub(score=0.0, verdict="error"),
        slot_payload={"skill": "broken", "input": {}, "result": ""},
        rubric_sha="abc",
        status="error",
        error_message="TimeoutExpired: claude -p stuck",
    )
    out_dir = write_run_artifacts(art)
    fm = (out_dir / "report.md").read_text()
    assert "status: error" in fm
    assert "error_message: TimeoutExpired" in fm


def test_atomic_append_index_concurrent_processes(tmp_path):
    """评审 S-04：fcntl.flock 是 per-process 锁，必须用进程而非线程才能验真原子性。"""
    idx = tmp_path / "INDEX.md"
    lines = [f"line-{i}-{'x' * 100}" for i in range(50)]  # 长行更易触发交错
    procs = [mp.Process(target=atomic_append_index, args=(idx, line)) for line in lines]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=10)
    written = idx.read_text().splitlines()
    assert sorted(written) == sorted(lines)
    assert len(written) == 50  # 无丢失 / 无重复 / 无截断


def test_index_line_format(tmp_path):
    """index_line 含 status 列（评审 S-02）"""
    art = RunArtifacts(
        skill_dir=tmp_path, skill_name="foo",
        run_id="1748940000-abc-001", sid="abc12345",
        slot_idx=1, judge=_judge_stub(),
        slot_payload={}, rubric_sha="xyz",
    )
    line = index_line(art, tools_used=["Read", "Glob"], suggestion_count=2)
    assert line.startswith("1748940000-abc-001 | 0.82 | good")
    assert "status=ok" in line
    assert "sid=abc12345" in line
    assert "tools=Read,Glob" in line
    assert "suggestions=2" in line


def test_index_line_no_tools(tmp_path):
    art = RunArtifacts(
        skill_dir=tmp_path, skill_name="foo",
        run_id="x", sid="y", slot_idx=0, judge=_judge_stub(),
        slot_payload={}, rubric_sha="z",
    )
    assert "tools=-" in index_line(art, tools_used=[], suggestion_count=0)
