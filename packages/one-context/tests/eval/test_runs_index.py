"""Tests for runs_index.py (Stage 2.5.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.eval import runs_index as RI


def _make_run(reports_dir: Path, run_id: str, *, overall: str,
              score: float, cost: float, duration_ms: int,
              timestamp: str) -> Path:
    rdir = reports_dir / run_id
    rdir.mkdir(parents=True)
    run = {
        "run_id":         run_id,
        "skill":          "demo",
        "scenario":       "case",
        "overall":        overall,
        "timestamp":      timestamp,
        "git_commit":     "abc12345",
        "requested_model": "claude-opus-4-7",
        "actual_model":    "claude-opus-4-7",
        "duration_ms":    duration_ms,
        "cost_usd":       cost,
        "provider_status": "ok" if overall == "PASS" else "api_error",
        "threshold":      0.8,
        "tool_calls":     [{"name": "Read"}, {"name": "Write"}],
        "artifacts":      [{"path": "out.md", "size": 100, "sha256": "x"}],
        "judge": {
            "model":  "haiku",
            "pass":   overall == "PASS",
            "score":  score,
            "reason": "ok",
            "criteria": "- crit 1\n- crit 2",
            "cached": False,
        },
    }
    (rdir / "run.json").write_text(json.dumps(run), encoding="utf-8")
    return rdir


def test_render_runs_index_empty(tmp_path: Path) -> None:
    scn = tmp_path / "scn"
    scn.mkdir()
    out = RI.render_runs_index(scenario_dir=scn, skill="demo", scenario="case")
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "demo" in html and "case" in html
    assert "No runs yet" in html
    assert "onecxt eval demo/case" in html


def test_render_runs_index_with_runs(tmp_path: Path) -> None:
    scn = tmp_path / "scn"
    reports = scn / "__reports"
    _make_run(reports, "1700000001-aaa", overall="PASS", score=0.92,
              cost=1.10, duration_ms=120_000, timestamp="2026-05-28T10:00:00Z")
    _make_run(reports, "1700000002-bbb", overall="FAIL", score=0.55,
              cost=0.50, duration_ms=60_000,  timestamp="2026-05-29T11:00:00Z")
    _make_run(reports, "1700000003-ccc", overall="PASS", score=0.98,
              cost=2.40, duration_ms=166_646, timestamp="2026-05-30T01:35:00Z")

    out = RI.render_runs_index(scenario_dir=scn, skill="demo", scenario="case")
    html = out.read_text(encoding="utf-8")

    # all 3 runs surfaced
    for rid in ("1700000001-aaa", "1700000002-bbb", "1700000003-ccc"):
        assert rid in html

    # newest first: 'ccc' should appear before 'bbb' which appears before 'aaa'
    idx_aaa = html.index("1700000001-aaa")
    idx_bbb = html.index("1700000002-bbb")
    idx_ccc = html.index("1700000003-ccc")
    assert idx_ccc < idx_bbb < idx_aaa

    # aggregate stats: 2 PASS / 1 FAIL → 67% pass rate
    assert "67%" in html
    # total cost = 1.10 + 0.50 + 2.40 = 4.00 → $4.00
    assert "$4.00" in html
    # avg score ≈ (0.92 + 0.55 + 0.98) / 3 = 0.8166… → rounded to 0.817
    assert "0.817" in html
    # PASS / FAIL visual markers
    assert "text-emerald-400" in html
    assert "text-rose-400" in html
    # rows link to per-run report.html
    assert "1700000003-ccc/report.html" in html


def test_render_runs_index_missing_scenario(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RI.render_runs_index(
            scenario_dir=tmp_path / "missing",
            skill="x", scenario="y",
        )


def test_render_runs_index_handles_skipped_judge(tmp_path: Path) -> None:
    """Provider-failed runs (judge skipped) should still appear in the table."""
    scn = tmp_path / "scn"
    reports = scn / "__reports"
    rdir = reports / "1700000099-zzz"
    rdir.mkdir(parents=True)
    (rdir / "run.json").write_text(json.dumps({
        "run_id": "1700000099-zzz",
        "overall": "FAIL",
        "timestamp": "2026-06-01T00:00:00Z",
        "provider_status": "api_error",
        "duration_ms": 800,
        "cost_usd": 0.0,
        "judge": {"skipped": "provider_failed"},
    }), encoding="utf-8")

    out = RI.render_runs_index(scenario_dir=scn, skill="demo", scenario="case")
    html = out.read_text(encoding="utf-8")
    assert "1700000099-zzz" in html
    # skipped score renders as em-dash placeholder
    assert "—" in html
