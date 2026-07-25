"""Baseline snapshot management (Stage 2.1).

A "snapshot" promotes the *latest* ``__reports/<runId>/`` of a
scenario into ``__baselines/`` so future ``--diff`` runs have a
stable reference. The promotion rules (tech_design §4.2 / plan
Stage 2.1):

  - Source run must be ``overall == "PASS"``.
  - Source run must NOT have a ``skill_override`` field — override
    runs are debug artifacts, never authoritative.
  - ``__baselines/`` is replaced wholesale (no merge): copy every
    file from the source report dir, then write ``baseline.json``
    = source ``run.json`` + ``{snapshot_reason, snapshot_run_id,
    snapshot_at, target_path_sha256_at_snapshot}``.

A baseline is one-per-scenario by design; we only keep the latest
explicit snapshot. The source ``__reports/<runId>/`` is left intact.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SnapshotOutcome:
    scenario_dir: Path
    source_run_id: str
    source_report_dir: Path
    baseline_dir: Path
    baseline_json_path: Path


class SnapshotError(Exception):
    """Snapshot was refused (not PASS / override run / no run yet)."""


def _latest_run_dir(scenario_dir: Path) -> Path | None:
    """Return the ``__reports/<runId>/`` with the highest runId.

    runId format is ``<unix_seconds>-<6char>`` (sandbox.new_run_id),
    so lexicographic sort on the directory name is equivalent to
    chronological order. Skip dirs without a ``run.json`` (in-progress
    or corrupt).
    """
    reports = scenario_dir / "__reports"
    if not reports.is_dir():
        return None
    candidates = sorted(
        (p for p in reports.iterdir()
         if p.is_dir() and (p / "run.json").is_file()),
        key=lambda p: p.name,
    )
    return candidates[-1] if candidates else None


def _load_run_json(run_dir: Path) -> dict:
    with (run_dir / "run.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def snapshot(
    *,
    scenario_dir: Path,
    reason: str,
    source_run_id: str | None = None,
    now: datetime | None = None,
) -> SnapshotOutcome:
    """Promote the latest (or given) report into ``__baselines/``.

    Args:
        scenario_dir: ``skills/<skill>/evals/<scenario>/``.
        reason: human-readable text explaining why this snapshot was
            taken; persisted into ``baseline.json``.
        source_run_id: pin to a specific runId; default = latest.
        now: injected for deterministic tests.

    Raises:
        SnapshotError: source run missing / not PASS / override run.
    """
    if not reason or not reason.strip():
        raise SnapshotError("--reason is required and must be non-empty")

    if source_run_id is None:
        src = _latest_run_dir(scenario_dir)
        if src is None:
            raise SnapshotError(
                f"no runs to snapshot under {scenario_dir / '__reports'}"
            )
    else:
        src = scenario_dir / "__reports" / source_run_id
        if not (src / "run.json").is_file():
            raise SnapshotError(f"runId not found: {source_run_id}")

    run = _load_run_json(src)
    overall = run.get("overall", "")
    if overall != "PASS":
        raise SnapshotError(
            f"refuse to snapshot a {overall or 'unknown'} run "
            f"({src.name}); snapshot only PASS"
        )
    if run.get("skill_override"):
        raise SnapshotError(
            f"refuse to snapshot a --skill-override run ({src.name}); "
            f"override runs are debug artifacts"
        )

    baseline_dir = scenario_dir / "__baselines"
    if baseline_dir.exists():
        shutil.rmtree(baseline_dir)
    # copytree preserves the report tree (artifacts/, inputs/,
    # stream-json.jsonl, judge-cache/, report.html, run.json, ...).
    shutil.copytree(src, baseline_dir)

    # baseline.json = source run.json + snapshot_* metadata, written
    # alongside the copied run.json (we keep run.json untouched so
    # diff tooling can compare run.json ↔ run.json directly).
    now = now or datetime.now(timezone.utc)
    baseline = dict(run)
    baseline["snapshot_reason"] = reason.strip()
    baseline["snapshot_run_id"] = run["run_id"]
    baseline["snapshot_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    baseline["target_path_sha256_at_snapshot"] = run.get(
        "target_path_sha256", ""
    )
    baseline_json_path = baseline_dir / "baseline.json"
    with baseline_json_path.open("w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return SnapshotOutcome(
        scenario_dir=scenario_dir,
        source_run_id=run["run_id"],
        source_report_dir=src,
        baseline_dir=baseline_dir,
        baseline_json_path=baseline_json_path,
    )
