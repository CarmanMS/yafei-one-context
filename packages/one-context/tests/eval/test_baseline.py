"""Stage 2.1 — baseline.snapshot() unit tests.

Covers:
  - latest run picked when source_run_id is None
  - source_run_id pin path
  - PASS guard refuses FAIL / unknown / empty
  - skill_override guard refuses override runs
  - reason required + stripped
  - baseline.json fields exact (snapshot_reason / _run_id / _at /
    target_path_sha256_at_snapshot)
  - whole report tree copied (artifacts/ + inputs/ + report.html)
  - second snapshot replaces the first (no merge / stale files)
  - source __reports/<runId>/ left intact
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from one_context.eval.baseline import (
    SnapshotError,
    SnapshotOutcome,
    snapshot,
)


def _write_run(
    scenario_dir: Path,
    run_id: str,
    *,
    overall: str = "PASS",
    target_path_sha256: str = "abc123",
    skill_override: dict | None = None,
    extras: dict | None = None,
) -> Path:
    """Create a fake __reports/<runId>/ with a minimal but realistic tree."""
    run_dir = scenario_dir / "__reports" / run_id
    run_dir.mkdir(parents=True)
    run = {
        "run_schema_version": "1",
        "skill": "demo",
        "scenario": "scn",
        "run_id": run_id,
        "overall": overall,
        "target_path_sha256": target_path_sha256,
    }
    if skill_override is not None:
        run["skill_override"] = skill_override
    if extras:
        run.update(extras)
    (run_dir / "run.json").write_text(
        json.dumps(run, indent=2), encoding="utf-8"
    )
    (run_dir / "report.html").write_text("<html>fake</html>", encoding="utf-8")
    (run_dir / "stream-json.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "artifacts").mkdir()
    (run_dir / "artifacts" / "out.md").write_text("artifact", encoding="utf-8")
    (run_dir / "inputs").mkdir()
    (run_dir / "inputs" / "ground_truth").mkdir()
    (run_dir / "inputs" / "ground_truth" / "pass-01.yaml").write_text(
        "kind: pass\n", encoding="utf-8",
    )
    return run_dir


def test_snapshot_latest_pass_run(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    # newer runId (higher unix prefix) wins regardless of mtime
    _write_run(scn, "1000000000-aaaaaa", overall="PASS",
               target_path_sha256="sha_old")
    _write_run(scn, "2000000000-bbbbbb", overall="PASS",
               target_path_sha256="sha_new")

    fixed_now = datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)
    out = snapshot(scenario_dir=scn, reason="  initial pass  ", now=fixed_now)

    assert isinstance(out, SnapshotOutcome)
    assert out.source_run_id == "2000000000-bbbbbb"
    assert out.baseline_dir == scn / "__baselines"
    assert out.baseline_json_path == scn / "__baselines" / "baseline.json"

    baseline = json.loads(out.baseline_json_path.read_text(encoding="utf-8"))
    assert baseline["snapshot_reason"] == "initial pass"
    assert baseline["snapshot_run_id"] == "2000000000-bbbbbb"
    assert baseline["snapshot_at"] == "2026-05-30T12:00:00Z"
    assert baseline["target_path_sha256_at_snapshot"] == "sha_new"
    # original run fields are preserved
    assert baseline["run_id"] == "2000000000-bbbbbb"
    assert baseline["overall"] == "PASS"


def test_snapshot_copies_whole_report_tree(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="PASS")

    snapshot(scenario_dir=scn, reason="x")

    bdir = scn / "__baselines"
    assert (bdir / "run.json").is_file()
    assert (bdir / "report.html").read_text(encoding="utf-8") == "<html>fake</html>"
    assert (bdir / "stream-json.jsonl").is_file()
    assert (bdir / "artifacts" / "out.md").read_text(encoding="utf-8") == "artifact"
    assert (bdir / "inputs" / "ground_truth" / "pass-01.yaml").is_file()
    # baseline.json sits alongside the original run.json (not replacing it)
    assert (bdir / "baseline.json").is_file()
    assert (bdir / "run.json").is_file()


def test_snapshot_pinned_run_id(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="PASS",
               target_path_sha256="sha_old")
    _write_run(scn, "2000000000-bbbbbb", overall="PASS",
               target_path_sha256="sha_new")

    out = snapshot(scenario_dir=scn, reason="pin older",
                   source_run_id="1000000000-aaaaaa")
    assert out.source_run_id == "1000000000-aaaaaa"
    baseline = json.loads(out.baseline_json_path.read_text(encoding="utf-8"))
    assert baseline["target_path_sha256_at_snapshot"] == "sha_old"


def test_snapshot_pinned_run_id_missing(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="PASS")
    with pytest.raises(SnapshotError, match="runId not found"):
        snapshot(scenario_dir=scn, reason="x",
                 source_run_id="9999999999-zzzzzz")


def test_snapshot_refuses_fail_run(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="FAIL")
    with pytest.raises(SnapshotError, match="refuse to snapshot a FAIL run"):
        snapshot(scenario_dir=scn, reason="x")
    # baseline must NOT have been created
    assert not (scn / "__baselines").exists()


def test_snapshot_refuses_override_run(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="PASS",
               skill_override={"dir": "/tmp/override", "files": ["SKILL.md"]})
    with pytest.raises(SnapshotError, match="--skill-override run"):
        snapshot(scenario_dir=scn, reason="x")
    assert not (scn / "__baselines").exists()


def test_snapshot_refuses_empty_reason(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="PASS")
    for bad in ("", "   ", "\n"):
        with pytest.raises(SnapshotError, match="--reason is required"):
            snapshot(scenario_dir=scn, reason=bad)


def test_snapshot_refuses_no_runs(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    with pytest.raises(SnapshotError, match="no runs to snapshot"):
        snapshot(scenario_dir=scn, reason="x")


def test_snapshot_replaces_previous(tmp_path: Path) -> None:
    """Second snapshot must not leave stale files from the first."""
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    _write_run(scn, "1000000000-aaaaaa", overall="PASS",
               target_path_sha256="sha_v1")
    snapshot(scenario_dir=scn, reason="v1")
    # Sentinel file injected only in the v1 baseline; should vanish on v2.
    (scn / "__baselines" / "stale-only-in-v1.txt").write_text("stale")

    _write_run(scn, "2000000000-bbbbbb", overall="PASS",
               target_path_sha256="sha_v2")
    snapshot(scenario_dir=scn, reason="v2")

    assert not (scn / "__baselines" / "stale-only-in-v1.txt").exists()
    baseline = json.loads(
        (scn / "__baselines" / "baseline.json").read_text(encoding="utf-8"))
    assert baseline["snapshot_reason"] == "v2"
    assert baseline["target_path_sha256_at_snapshot"] == "sha_v2"


def test_snapshot_leaves_source_intact(tmp_path: Path) -> None:
    scn = tmp_path / "skills" / "demo" / "evals" / "scn"
    scn.mkdir(parents=True)
    src = _write_run(scn, "1000000000-aaaaaa", overall="PASS")
    snapshot(scenario_dir=scn, reason="x")
    # source __reports/<runId>/ still fully present
    assert (src / "run.json").is_file()
    assert (src / "artifacts" / "out.md").is_file()
    assert (src / "inputs" / "ground_truth" / "pass-01.yaml").is_file()
