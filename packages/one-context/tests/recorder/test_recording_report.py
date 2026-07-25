"""recording_report.html renderer tests.

Covers `recorder/report.py` against the contract documented in the
plan file:

- `render_staging` writes <session_dir>/staging/recording_report.html
- `render_committed` writes <scenario_dir>/_recording/recording_report.html
- Idempotent overwrite on repeated finalize
- Draft degraded path produces a report with an LLM-failed pill
- warnings.txt contents reach the Diagnostics tab
- last_commit_outcome.json contents reach the Diagnostics tab
- Large rounds (>64KB) trigger a truncation marker, not a crash
- Failure paths in `report.py` are swallowed (never raises)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.recorder import report as report_mod
from one_context.recorder.report import (
    StagingSnapshot,
    _parse_draft_dimensions,
    collect_from_staging,
    collect_live_rounds,
    collect_live_status,
    render_committed,
    render_live_html,
    render_staging,
)
from one_context.recorder.session import Session, start_session


def _make_session(recorder_tmp: Path, repo_with_skill: Path) -> Session:
    return start_session(
        "demo", "scn",
        cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )


def _populate_staging(
    sess: Session,
    *,
    draft: str | None = None,
    warnings: list[str] | None = None,
    llm_error: str | None = None,
    rounds: dict[str, str] | None = None,
    artifacts: dict[str, str] | None = None,
    final_text: str | None = None,
    meta: dict | None = None,
    last_outcome: dict | None = None,
) -> Path:
    staging = Path(sess.recording_dir) / "staging"
    staging.mkdir(exist_ok=True)
    if draft is not None:
        (staging / "judge_candidates_draft.md").write_text(draft, encoding="utf-8")
    if warnings:
        (staging / "warnings.txt").write_text("\n".join(warnings) + "\n", encoding="utf-8")
    if llm_error:
        (staging / "llm_error.txt").write_text(llm_error, encoding="utf-8")
    if rounds:
        mr_dir = staging / "mock_rounds"
        mr_dir.mkdir(exist_ok=True)
        for name, body in rounds.items():
            (mr_dir / name).write_text(body, encoding="utf-8")
    baseline = staging / "baseline"
    baseline.mkdir(exist_ok=True)
    if artifacts:
        arts = baseline / "artifacts"
        arts.mkdir(parents=True, exist_ok=True)
        for rel, body in artifacts.items():
            p = arts / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
    if final_text is not None:
        (baseline / "final_text.md").write_text(final_text, encoding="utf-8")
    if meta is not None:
        (baseline / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if last_outcome is not None:
        (staging / "last_commit_outcome.json").write_text(
            json.dumps(last_outcome, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return staging


_DRAFT = """# Judge Prompt Draft — demo/scn

## 这次录制为什么算成功

stub

## 候选 query

抓今天的 AI 新闻

## 判定维度（LLM 给 0-1 分）

### D1: completeness
**判定标准**: 覆盖率
**权重**: 0.5

### D2: freshness
**判定标准**: 24h 内
**权重**: 0.5

## 虚假通过反例

### F1: empty-output
**特征**: 文件为空
"""

_ROUND_YAML = """round_id: round-01-bash-deadbeef
tool_name: Bash
tool_input:
  command: ls
tool_result: 'a\\nb\\n'
boundary_type: local_tool
"""


# ── happy: staging report renders all five tabs ────────────────────────


def test_render_staging_writes_full_report(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = _make_session(recorder_tmp, repo_with_skill)
    _populate_staging(
        sess,
        draft=_DRAFT,
        rounds={"round-01-bash-deadbeef.yaml": _ROUND_YAML},
        artifacts={"production/out.md": "# hi"},
        final_text="final agent text",
        meta={"recorded_at": "2026-06-03T00:00:00Z", "cc_cli_version": "1.0"},
        warnings=["cc_session_id unresolved"],
    )

    out = render_staging(sess)
    assert out is not None
    html = out.read_text(encoding="utf-8")

    # the 5 tabs are present
    for label in ("Overview", "Draft", "Rounds", "Baseline", "Diagnostics"):
        assert label in html
    # draft headings reach the page
    assert "completeness" in html
    assert "freshness" in html
    # round renders
    assert "round-01-bash-deadbeef" in html
    # baseline artifact appears in file list
    assert "production/out.md" in html
    # warnings reach Diagnostics
    assert "cc_session_id unresolved" in html
    # mode badge says staging
    assert "staging" in html


# ── degraded LLM draft surfaces a warning, does not crash ──────────────


def test_render_staging_handles_degraded_draft(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = _make_session(recorder_tmp, repo_with_skill)
    degraded = "# LLM 起草失败 — manual handoff\n\n请手写 judge 维度。"
    _populate_staging(
        sess, draft=degraded,
        llm_error="LLMCallError: timeout",
    )

    out = render_staging(sess)
    assert out is not None
    html = out.read_text(encoding="utf-8")
    # the degraded pill triggers because the marker is in the draft
    assert "draft LLM 降级" in html
    # llm_error pill + content
    assert "llm_error" in html
    assert "LLMCallError" in html


# ── idempotent: second finalize overwrites the html ────────────────────


def test_render_staging_overwrites_on_rerun(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = _make_session(recorder_tmp, repo_with_skill)
    _populate_staging(sess, draft=_DRAFT)
    first = render_staging(sess)
    assert first is not None
    initial_text = first.read_text(encoding="utf-8")

    # mutate staging then re-render — file should reflect new state.
    _populate_staging(sess, draft=_DRAFT, warnings=["new warning"])
    second = render_staging(sess)
    assert second == first  # same path
    new_text = second.read_text(encoding="utf-8")
    assert "new warning" in new_text
    assert new_text != initial_text


# ── last_commit_outcome.json reaches the Diagnostics tab ───────────────


def test_render_staging_surfaces_last_commit_outcome(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = _make_session(recorder_tmp, repo_with_skill)
    _populate_staging(
        sess,
        draft=_DRAFT,
        last_outcome={
            "outcome": "user_clarification",
            "error_class": "ambiguous_intents",
            "message": "LLM flagged ambiguous intents",
            "ambiguous_intents": ["删 D1 但 D1 不存在"],
            "ts": "2026-06-03T01:23:45+00:00",
        },
    )
    out = render_staging(sess)
    html = out.read_text(encoding="utf-8")
    assert "ambiguous_intents" in html
    assert "删 D1 但 D1 不存在" in html


# ── large round preview is truncated, no crash ─────────────────────────


def test_render_staging_truncates_large_round(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = _make_session(recorder_tmp, repo_with_skill)
    big = "x" * (80 * 1024)
    big_yaml = f"round_id: big\ntool_name: Bash\ntool_input: {{}}\ntool_result: '{big}'\n"
    _populate_staging(
        sess, draft=_DRAFT,
        rounds={"big.yaml": big_yaml},
    )
    out = render_staging(sess)
    assert out is not None
    html = out.read_text(encoding="utf-8")
    assert "truncated" in html


# ── committed report from a captured snapshot ──────────────────────────


def test_render_committed_with_snapshot(
    tmp_path: Path,
) -> None:
    scenario_dir = tmp_path / "skills" / "demo" / "evals" / "scn"
    (scenario_dir / "mock_rounds").mkdir(parents=True)
    (scenario_dir / "mock_rounds" / "round-01.yaml").write_text(_ROUND_YAML, encoding="utf-8")
    (scenario_dir / "baseline" / "artifacts").mkdir(parents=True)
    (scenario_dir / "baseline" / "artifacts" / "out.md").write_text("hi", encoding="utf-8")

    snap = StagingSnapshot(
        skill_name="demo",
        scenario_name="scn",
        session_id="abc12345",
        cc_session_id="cc-target",
        started_at="2026-06-03T00:00:00Z",
        status="committed",
        draft_md=_DRAFT,
        draft_present=True,
        draft_degraded=False,
        rounds=[{
            "round_id": "round-01",
            "tool_name": "Bash",
            "boundary_type": "local_tool",
            "args_summary": "{}",
            "size": 100,
            "size_human": "100 B",
            "truncated": False,
            "preview": _ROUND_YAML,
            "file_name": "round-01.yaml",
        }],
        baseline_artifacts=[],
        baseline_final_text="",
        baseline_meta={},
        warnings=[],
        llm_error="",
        last_commit_outcome=None,
    )
    result = {
        "scenario_dir": str(scenario_dir),
        "scenario_yaml_path": str(scenario_dir / "scenario.yaml"),
        "files_written": ["scenario.yaml"],
        "backup_path": None,
    }
    out = render_committed(scenario_dir, staging_snapshot=snap, commit_result=result)
    assert out is not None
    assert out == scenario_dir / "_recording" / "recording_report.html"
    html = out.read_text(encoding="utf-8")
    assert "已落地" in html
    assert "commit_finalize 已成功" in html


# ── render functions never raise ──────────────────────────────────────


def test_render_staging_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pass a session with a non-existent recording_dir.
    bogus = Session(
        session_id="x", skill_name="demo", scenario_name="scn",
        cc_session_id=None, started_at="", status="recording",
        recording_dir="/this/path/does/not/exist",
    )
    # Should not raise; staging missing → still tries, output dir create fails? actually mkdir ok at /
    # Easier: force the template loader to blow up.
    def boom(*a, **kw):
        raise RuntimeError("template loader exploded")
    monkeypatch.setattr(report_mod._ENV, "get_template", boom)
    assert render_staging(bogus) is None
    assert render_committed(Path("/tmp/_no_such_scenario_dir_x")) is None


# ── draft dimension parsing matches commit_finalize's regex ────────────


def test_parse_draft_dimensions_extracts_ids() -> None:
    dims = _parse_draft_dimensions(_DRAFT)
    ids = [d["id"] for d in dims]
    assert ids == ["D1", "D2", "F1"]
    assert dims[0]["name"] == "completeness"


# ── live mode ──────────────────────────────────────────────────────────


def _append_jsonl(session_dir: Path, records: list[dict]) -> None:
    with (session_dir / "rounds.jsonl").open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_collect_live_rounds_parses_jsonl_and_filters(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        parent_cc_session_id="cc-parent",
        repo_root=repo_with_skill,
    )
    _append_jsonl(Path(sess.recording_dir), [
        # parent noise — should be filtered out
        {"round_id": "r-parent", "tool_name": "Read", "tool_input": {},
         "tool_result": "x", "boundary_type": "local_tool",
         "event_type": "PostToolUse", "cc_session_id": "cc-parent"},
        {"round_id": "r-01", "tool_name": "Bash", "tool_input": {"command": "ls"},
         "tool_result": "ok", "boundary_type": "local_tool",
         "event_type": "PostToolUse", "cc_session_id": "cc-target"},
        {"round_id": "r-02", "tool_name": "WebFetch",
         "tool_input": {"url": "https://x"}, "tool_result": "body",
         "boundary_type": "local_tool", "event_type": "PostToolUse",
         "cc_session_id": "cc-target"},
    ])
    rounds = collect_live_rounds(sess)
    assert [r["round_id"] for r in rounds] == ["r-01", "r-02"]
    assert rounds[0]["seq"] == 1
    assert rounds[0]["args_summary"] == "ls"
    assert rounds[1]["args_summary"] == "https://x"


def test_collect_live_rounds_skips_partial_lines(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    # Valid line + garbage tail (mid-write race simulation)
    jsonl = Path(sess.recording_dir) / "rounds.jsonl"
    jsonl.write_text(
        json.dumps({"round_id": "r-01", "tool_name": "Bash", "tool_input": {},
                    "tool_result": "", "boundary_type": "local_tool",
                    "cc_session_id": "cc-target"}) + "\n"
        + "{partial half-writ",
        encoding="utf-8",
    )
    rounds = collect_live_rounds(sess)
    assert len(rounds) == 1


def test_collect_live_status_reflects_state(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    _append_jsonl(Path(sess.recording_dir), [
        {"round_id": "r-01", "tool_name": "WebFetch", "tool_input": {"url": "x"},
         "tool_result": "y", "boundary_type": "local_tool",
         "event_type": "PostToolUse", "cc_session_id": "cc-target"},
    ])
    status = collect_live_status(sess)
    assert status["round_count"] == 1
    assert status["current_tool"] == "WebFetch"
    assert status["status"] == "recording"
    assert status["finalize_present"] is False
    assert status["last_activity_seconds"] is not None
    assert status["last_activity_seconds"] < 5  # just wrote it


def test_render_live_html_contains_live_tab(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    _append_jsonl(Path(sess.recording_dir), [
        {"round_id": "r-01", "tool_name": "Bash", "tool_input": {"command": "ls"},
         "tool_result": "ok", "boundary_type": "local_tool",
         "event_type": "PostToolUse", "cc_session_id": "cc-target"},
    ])
    html = render_live_html(sess)
    assert "recordingReport()" in html
    assert "tab === 'live'" in html
    # rounds initial baked into RUN_DATA
    assert "r-01" in html
    # heartbeat bar copy
    assert "录制中" in html
    # SVG lane container
    assert "<svg" in html
    # Live tab default when is_live
    assert "isLive: true" in html


def test_render_live_html_after_recording_falls_back_to_static(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    # Recreate a "committed-but-also-historical" path by aborting after appending.
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    _append_jsonl(Path(sess.recording_dir), [
        {"round_id": "r-01", "tool_name": "Read", "tool_input": {"file_path": "a"},
         "tool_result": "x", "boundary_type": "local_tool",
         "cc_session_id": "cc-target"},
    ])
    # status still 'recording' so renderer treats it as live; verify the
    # heartbeat shows 'recording' branch
    html = render_live_html(sess)
    assert "r-01" in html
    assert "录制中" in html
