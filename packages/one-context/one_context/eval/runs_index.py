"""Multi-run aggregate page (Stage 2.5.4).

Walks ``skills/<skill>/evals/<scenario>/__reports/*/run.json`` and renders
a single ``__reports/index.html`` listing every run with verdict / score /
cost / duration / timestamp. Each row links to that run's ``report.html``.

CLI:
    onecxt eval runs <skill>/<scenario>

The page is regenerated from scratch each invocation — no incremental
state, no diffing across runs. Good enough for "show me the trend on
this scenario over the last week" use case.

NOTE: ``onecxt eval`` PASS-rolls ``__reports/``: when a scenario passes,
every older runId and ``index.html`` are deleted. So the trend you see
here only spans the FAIL streak since the last PASS. If you want to keep
a longer history, copy ``index.html`` (or the runs you care about) out
before running another evaluation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
    lstrip_blocks=False,
)


def _fmt_duration(ms: int | float | None) -> str:
    if ms is None:
        return "—"
    ms = int(ms)
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s"
    m, s = divmod(ms // 1000, 60)
    return f"{m}:{s:02d}"


def _fmt_cost(usd: float | None) -> str:
    if usd is None:
        return "—"
    return f"${usd:.2f}"


def _collect_runs(reports_dir: Path) -> list[dict[str, Any]]:
    """Read every ``<reports_dir>/*/run.json``; sort newest first."""
    if not reports_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(reports_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        rj = run_dir / "run.json"
        if not rj.is_file():
            continue
        try:
            run = json.loads(rj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        judge = run.get("judge") or {}
        rows.append({
            "run_id":      run.get("run_id", run_dir.name),
            "timestamp":   run.get("timestamp", ""),
            "overall":     run.get("overall", "?"),
            "overall_pass": run.get("overall") == "PASS",
            "score":       judge.get("score"),
            "threshold":   run.get("threshold"),
            "judge_pass":  judge.get("pass"),
            "judge_skipped": "skipped" in judge and "model" not in judge,
            "cost_usd":    run.get("cost_usd"),
            "cost_human":  _fmt_cost(run.get("cost_usd")),
            "duration_ms": run.get("duration_ms"),
            "duration_human": _fmt_duration(run.get("duration_ms")),
            "git_commit":  run.get("git_commit", ""),
            "actual_model": run.get("actual_model") or run.get("requested_model", ""),
            "provider_status": run.get("provider_status", "?"),
            "model_drift": run.get("model_drift", False),
            "report_href": f"{run_dir.name}/report.html",
            "run_json_href": f"{run_dir.name}/run.json",
            "tool_calls_count": len(run.get("tool_calls") or []),
            "artifact_count":   len(run.get("artifacts") or []),
        })
    # newest first (timestamp lexicographically descending — ISO8601 sorts right)
    rows.sort(key=lambda r: r["timestamp"], reverse=True)
    return rows


def render_runs_index(*, scenario_dir: Path, skill: str, scenario: str) -> Path:
    """Render ``__reports/index.html`` and return its path.

    Raises FileNotFoundError when the scenario dir is missing.
    """
    if not scenario_dir.is_dir():
        raise FileNotFoundError(f"scenario dir missing: {scenario_dir}")
    reports_dir = scenario_dir / "__reports"
    runs = _collect_runs(reports_dir)

    # aggregate stats
    total = len(runs)
    passed = sum(1 for r in runs if r["overall_pass"])
    pass_rate_pct = int(round(passed / total * 100)) if total else 0
    scores = [r["score"] for r in runs if isinstance(r["score"], (int, float))]
    avg_score = round(sum(scores) / len(scores), 3) if scores else None
    costs = [r["cost_usd"] for r in runs if isinstance(r["cost_usd"], (int, float))]
    total_cost = round(sum(costs), 4) if costs else 0.0
    durations = [r["duration_ms"] for r in runs if isinstance(r["duration_ms"], (int, float))]
    avg_dur_ms = round(sum(durations) / len(durations)) if durations else None

    view = {
        "skill":         skill,
        "scenario":      scenario,
        "generated_at":  datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "runs":          runs,
        "total":         total,
        "passed":        passed,
        "failed":        total - passed,
        "pass_rate_pct": pass_rate_pct,
        "avg_score":     avg_score,
        "total_cost":    total_cost,
        "total_cost_human": _fmt_cost(total_cost),
        "avg_duration_human": _fmt_duration(avg_dur_ms),
    }

    template = _ENV.get_template("runs_index.html.j2")
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / "index.html"
    out.write_text(template.render(**view), encoding="utf-8")
    return out
