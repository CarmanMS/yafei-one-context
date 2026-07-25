"""Stage 2.2 — baseline vs current diff unit tests."""

from __future__ import annotations

import json
from pathlib import Path

from one_context.eval.diff import compute, load_baseline


def _run(
    *,
    run_id: str = "1000000000-aaaaaa",
    judge_score: float = 0.9,
    judge_pass: bool = True,
    tool_calls: list[dict] | None = None,
    artifacts: list[dict] | None = None,
    final_text: str = "",
    actual_model: str = "claude-opus-4-7",
    target_path_sha256: str = "sha-abc",
    **extras,
) -> dict:
    base = {
        "run_id": run_id,
        "judge": {"score": judge_score, "pass": judge_pass},
        "tool_calls": tool_calls or [],
        "artifacts": artifacts or [],
        "final_text": final_text,
        "actual_model": actual_model,
        "requested_model": actual_model,
        "target_path_sha256": target_path_sha256,
    }
    base.update(extras)
    return base


# ──────────────────────── no baseline ────────────────────────

def test_no_baseline() -> None:
    d = compute(current_run=_run(), baseline_run=None)
    assert d == {
        "has_baseline": False,
        "note": "no baseline snapshot exists; run `onecxt eval "
                "<skill>/<scenario> snapshot --reason \"…\"` first",
    }


# ──────────────────────── judge ────────────────────────

def test_judge_score_delta_and_pass_flip() -> None:
    baseline = _run(judge_score=0.95, judge_pass=True)
    current  = _run(judge_score=0.40, judge_pass=False)
    d = compute(current_run=current, baseline_run=baseline)
    assert d["judge"]["score_delta"] == -0.55
    assert d["judge"]["pass_flipped"] is True
    assert d["judge"]["baseline_pass"] is True
    assert d["judge"]["current_pass"] is False


def test_judge_no_change() -> None:
    baseline = _run(judge_score=0.9, judge_pass=True)
    current  = _run(judge_score=0.9, judge_pass=True)
    d = compute(current_run=current, baseline_run=baseline)
    assert d["judge"]["score_delta"] == 0
    assert d["judge"]["pass_flipped"] is False


# ──────────────────────── tool_calls ────────────────────────

def test_tool_calls_sequence_unchanged() -> None:
    calls = [{"type": "Read"}, {"type": "Bash"}, {"type": "Write"}]
    d = compute(current_run=_run(tool_calls=calls),
                baseline_run=_run(tool_calls=list(calls)))
    tc = d["tool_calls"]
    assert tc["sequence_unchanged"] is True
    assert tc["total_delta"] == 0
    assert tc["by_type_delta"] == {}


def test_tool_calls_by_type_delta() -> None:
    baseline = _run(tool_calls=[{"type": "Read"}, {"type": "Read"},
                                {"type": "Bash"}, {"type": "Write"}])
    current  = _run(tool_calls=[{"type": "Read"}, {"type": "Bash"},
                                {"type": "Bash"}])  # -1 Read, +1 Bash, -1 Write
    d = compute(current_run=current, baseline_run=baseline)
    tc = d["tool_calls"]
    assert tc["sequence_unchanged"] is False
    assert tc["total_delta"] == -1
    assert tc["by_type_delta"] == {"Read": -1, "Bash": 1, "Write": -1}
    assert tc["baseline_by_type"] == {"Read": 2, "Bash": 1, "Write": 1}
    assert tc["current_by_type"]  == {"Read": 1, "Bash": 2}


def test_tool_calls_uses_name_when_type_missing() -> None:
    baseline = _run(tool_calls=[{"name": "Read"}])
    current  = _run(tool_calls=[{"name": "Bash"}])
    d = compute(current_run=current, baseline_run=baseline)
    assert d["tool_calls"]["by_type_delta"] == {"Read": -1, "Bash": 1}


# ──────────────────────── artifacts ────────────────────────

def test_artifacts_added_removed_changed() -> None:
    baseline = _run(artifacts=[
        {"path": "a.md", "size": 10, "sha256": "AAA"},
        {"path": "b.md", "size": 20, "sha256": "BBB"},
        {"path": "c.md", "size": 30, "sha256": "CCC"},
    ])
    current = _run(artifacts=[
        {"path": "a.md", "size": 10, "sha256": "AAA"},      # unchanged
        {"path": "b.md", "size": 25, "sha256": "BBB_NEW"},  # changed
        {"path": "d.md", "size": 40, "sha256": "DDD"},      # added (c removed)
    ])
    d = compute(current_run=current, baseline_run=baseline)
    arts = d["artifacts"]
    assert arts["added"]   == ["d.md"]
    assert arts["removed"] == ["c.md"]
    assert arts["unchanged_count"] == 1
    assert len(arts["changed"]) == 1
    chg = arts["changed"][0]
    assert chg["path"] == "b.md"
    assert chg["baseline_sha256"] == "BBB"
    assert chg["current_sha256"]  == "BBB_NEW"
    assert chg["baseline_size"] == 20
    assert chg["current_size"]  == 25


def test_artifacts_no_change() -> None:
    arts = [{"path": "a.md", "size": 1, "sha256": "X"}]
    d = compute(current_run=_run(artifacts=arts),
                baseline_run=_run(artifacts=list(arts)))
    assert d["artifacts"]["added"] == []
    assert d["artifacts"]["removed"] == []
    assert d["artifacts"]["changed"] == []
    assert d["artifacts"]["unchanged_count"] == 1


# ──────────────────────── final_text ────────────────────────

def test_final_text_unified_diff() -> None:
    baseline = _run(final_text="line A\nline B\nline C\n")
    current  = _run(final_text="line A\nline B-changed\nline C\n")
    d = compute(current_run=current, baseline_run=baseline)
    ft = d["final_text"]
    assert ft["changed"] is True
    assert "-line B" in ft["unified_diff"]
    assert "+line B-changed" in ft["unified_diff"]


def test_final_text_unchanged() -> None:
    d = compute(current_run=_run(final_text="x"),
                baseline_run=_run(final_text="x"))
    assert d["final_text"]["changed"] is False
    assert d["final_text"]["unified_diff"] == ""


# ──────────────────────── warnings ────────────────────────

def test_model_drift_warn() -> None:
    baseline = _run(actual_model="claude-opus-4-7")
    current  = _run(actual_model="claude-opus-4-8")
    d = compute(current_run=current, baseline_run=baseline)
    assert d["warnings"]["model_drift"]["drifted"] is True


def test_target_path_drift_uses_snapshot_field_when_present() -> None:
    baseline = _run(target_path_sha256="sha_old")
    baseline["target_path_sha256_at_snapshot"] = "sha_snap"
    current  = _run(target_path_sha256="sha_new")
    d = compute(current_run=current, baseline_run=baseline)
    w = d["warnings"]["target_path_drift"]
    assert w["drifted"] is True
    # the diff must compare against the snapshot fingerprint, NOT the
    # baseline run's runtime fingerprint
    assert w["baseline_sha256_at_snapshot"] == "sha_snap"
    assert w["current_sha256"] == "sha_new"


def test_target_path_no_drift() -> None:
    baseline = _run(target_path_sha256="sha_same")
    baseline["target_path_sha256_at_snapshot"] = "sha_same"
    current  = _run(target_path_sha256="sha_same")
    d = compute(current_run=current, baseline_run=baseline)
    assert d["warnings"]["target_path_drift"]["drifted"] is False


# ──────────────────────── provenance header ────────────────────────

def test_baseline_provenance_fields() -> None:
    baseline = _run(run_id="1000000000-aaaaaa")
    baseline["snapshot_run_id"] = "1000000000-aaaaaa"
    baseline["snapshot_at"] = "2026-05-30T06:00:00Z"
    baseline["snapshot_reason"] = "initial"
    d = compute(current_run=_run(run_id="2000000000-bbbbbb"),
                baseline_run=baseline)
    assert d["baseline"]["run_id"] == "1000000000-aaaaaa"
    assert d["baseline"]["snapshot_at"] == "2026-05-30T06:00:00Z"
    assert d["baseline"]["snapshot_reason"] == "initial"
    assert d["current"]["run_id"] == "2000000000-bbbbbb"


# ──────────────────────── load_baseline ────────────────────────

def test_load_baseline_missing(tmp_path: Path) -> None:
    assert load_baseline(tmp_path) is None


def test_load_baseline_present(tmp_path: Path) -> None:
    bdir = tmp_path / "__baselines"
    bdir.mkdir()
    (bdir / "baseline.json").write_text(
        json.dumps({"run_id": "x", "overall": "PASS"}),
        encoding="utf-8",
    )
    out = load_baseline(tmp_path)
    assert out == {"run_id": "x", "overall": "PASS"}
