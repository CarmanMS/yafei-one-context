"""HTML report rendering — round-trip a deterministic run.json."""

from __future__ import annotations

import json
from pathlib import Path

from one_context.eval import report as R


SAMPLE_RUN = {
    "run_schema_version": "1",
    "skill": "demo",
    "scenario": "case",
    "run_id": "1730000000-abc",
    "timestamp": "2026-05-29T12:00:00Z",
    "git_commit": "abc1234",
    "git_user_email": "a@b",
    "claude_cli_version": "2.1.156",
    "requested_model": "claude-sonnet-4-5",
    "actual_model": "claude-sonnet-4-5-20250901",
    "model_drift": False,
    "cwd": "features/x/",
    "fixture_mode": "overlay-and-replace",
    "overlay_replaced": ["features/x/spec.md"],
    "duration_ms": 1234,
    "exit_code": 0,
    "tool_calls": [
        {"name": "Write", "input": {"file_path": "features/x/out.md"}}
    ],
    "final_text": "done",
    "artifacts": [
        {"path": "production/out.md", "size": 12, "sha256": "abc" * 21 + "a"}
    ],
    "deleted_artifacts": [],
    "judge": {
        "model": "claude-haiku-4-5",
        "pass": True,
        "score": 0.9,
        "reason": "rubric satisfied",
        "criteria": "do the thing",
        "cached": False,
    },
    "threshold": 0.8,
    "repeat": {"total": 1, "passed": 1, "pass_rate": 1.0},
    "overall": "PASS",
}


def test_render_writes_html(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    R.render(SAMPLE_RUN, out)
    html = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    # title uses "skill / scenario"
    assert "demo / case" in html
    assert "PASS" in html
    # primary artifact path surfaced both in title bar and Alpine RUN_DATA
    assert "production/out.md" in html
    assert "rubric satisfied" in html
    # C4 verdict signal
    assert "text-emerald-400" in html
    # RUN_DATA payload injected
    assert "window.RUN_DATA" in html


def test_render_fail_uses_fail_class(tmp_path: Path) -> None:
    run = json.loads(json.dumps(SAMPLE_RUN))  # deep copy
    run["overall"] = "FAIL"
    run["judge"]["pass"] = False
    run["judge"]["score"] = 0.3
    run["judge"]["reason"] = "missing X"
    out = tmp_path / "r.html"
    R.render(run, out)
    html = out.read_text(encoding="utf-8")
    assert "FAIL" in html
    # C4 uses rose accents for failure (replaces Phase 1's "verdict fail" class)
    assert "text-rose-400" in html
    assert "bg-rose-500" in html
    assert "missing X" in html


def test_write_run_json_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "run.json"
    R.write_run_json(SAMPLE_RUN, out)
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["overall"] == "PASS"
    assert parsed["skill"] == "demo"


def test_render_omits_diff_tab_when_no_baseline_diff(tmp_path: Path) -> None:
    """When run.json has no baseline_diff key, Diff tab must not render."""
    out = tmp_path / "report.html"
    R.render(SAMPLE_RUN, out)
    html = out.read_text(encoding="utf-8")
    # tab id must not appear
    assert "id: 'diff'" not in html
    # panel marker must not appear
    assert "TAB: Diff (Stage 2.3)" not in html


def test_render_diff_tab_match(tmp_path: Path) -> None:
    """Identical baseline → MATCH badge + no warnings, sections present."""
    run = json.loads(json.dumps(SAMPLE_RUN))
    run["baseline_diff"] = {
        "has_baseline": True,
        "baseline": {
            "run_id":          "1700000000-zzz",
            "snapshot_at":     "2026-05-29T00:00:00Z",
            "snapshot_reason": "initial baseline",
            "target_path_sha256_at_snapshot": "sha-same",
        },
        "current": {
            "run_id":             run["run_id"],
            "target_path_sha256": "sha-same",
        },
        "judge": {
            "baseline_score": 0.9, "current_score": 0.9,
            "score_delta": 0.0,
            "baseline_pass": True, "current_pass": True,
            "pass_flipped": False,
        },
        "tool_calls": {
            "baseline_total": 1, "current_total": 1, "total_delta": 0,
            "sequence_unchanged": True,
            "by_type_delta": {},
            "baseline_by_type": {"Write": 1},
            "current_by_type":  {"Write": 1},
        },
        "artifacts": {
            "added": [], "removed": [], "changed": [], "unchanged_count": 1,
        },
        "final_text": {
            "changed": False, "baseline_size": 4, "current_size": 4,
            "unified_diff": "",
        },
        "warnings": {
            "model_drift": {"drifted": False, "baseline_model": "x", "current_model": "x"},
            "target_path_drift": {"drifted": False,
                                   "baseline_sha256_at_snapshot": "sha-same",
                                   "current_sha256": "sha-same"},
        },
    }
    out = tmp_path / "report.html"
    R.render(run, out)
    html = out.read_text(encoding="utf-8")
    assert "id: 'diff'" in html
    assert "TAB: Diff (Stage 2.3)" in html
    assert "MATCH" in html
    assert "sequence unchanged" in html
    # baseline provenance surfaces in the panel
    assert "1700000000-zzz" in html
    assert "initial baseline" in html
    # no drift warnings rendered
    assert "target_path drifted" not in html
    assert "actual_model drifted" not in html


def test_render_diff_tab_regress_with_warnings(tmp_path: Path) -> None:
    """Pass-flip + target_path drift + model drift → REGRESSION + warnings."""
    run = json.loads(json.dumps(SAMPLE_RUN))
    run["baseline_diff"] = {
        "has_baseline": True,
        "baseline": {
            "run_id":          "1700000000-zzz",
            "snapshot_at":     "2026-05-29T00:00:00Z",
            "snapshot_reason": "before refactor",
            "target_path_sha256_at_snapshot": "sha-old",
        },
        "current": {
            "run_id":             run["run_id"],
            "target_path_sha256": "sha-new",
        },
        "judge": {
            "baseline_score": 0.95, "current_score": 0.40,
            "score_delta": -0.55,
            "baseline_pass": True, "current_pass": False,
            "pass_flipped": True,
        },
        "tool_calls": {
            "baseline_total": 5, "current_total": 7, "total_delta": 2,
            "sequence_unchanged": False,
            "by_type_delta": {"Bash": 2},
            "baseline_by_type": {"Read": 3, "Bash": 2},
            "current_by_type":  {"Read": 3, "Bash": 4},
        },
        "artifacts": {
            "added": ["new.md"],
            "removed": ["old.md"],
            "changed": [{"path": "kept.md",
                         "baseline_size": 10, "current_size": 20,
                         "baseline_sha256": "AAAA1111",
                         "current_sha256":  "BBBB2222"}],
            "unchanged_count": 0,
        },
        "final_text": {
            "changed": True, "baseline_size": 4, "current_size": 9,
            "unified_diff": "--- baseline/final_text\n+++ current/final_text\n@@ -1 +1 @@\n-done\n+done now\n",
        },
        "warnings": {
            "model_drift": {"drifted": True, "baseline_model": "claude-opus-4-7",
                            "current_model": "claude-opus-4-8"},
            "target_path_drift": {"drifted": True,
                                   "baseline_sha256_at_snapshot": "sha-old",
                                   "current_sha256": "sha-new"},
        },
    }
    out = tmp_path / "report.html"
    R.render(run, out)
    html = out.read_text(encoding="utf-8")
    assert "REGRESSION" in html
    assert "pass flipped" in html
    assert "sequence changed" in html
    # warnings rendered
    assert "target_path drifted" in html
    assert "actual_model drifted" in html
    assert "claude-opus-4-7" in html and "claude-opus-4-8" in html
    # artifact diff entries rendered
    assert "new.md" in html
    assert "old.md" in html
    assert "kept.md" in html
    # unified diff body surfaces (escaped properly)
    assert "done now" in html


def test_render_diff_tab_no_baseline_message(tmp_path: Path) -> None:
    """--diff used but baseline missing → friendly explainer."""
    run = json.loads(json.dumps(SAMPLE_RUN))
    run["baseline_diff"] = {
        "has_baseline": False,
        "note": "no baseline snapshot exists; run `onecxt eval "
                "<skill>/<scenario> snapshot --reason \"…\"` first",
    }
    out = tmp_path / "report.html"
    R.render(run, out)
    html = out.read_text(encoding="utf-8")
    assert "id: 'diff'" in html
    assert "no baseline snapshot yet" in html
    assert "snapshot --reason" in html
