"""HTML report renderer (Stage 2.5.2 — C4 dashboard layout).

The template lives at ``templates/report.html.j2``. It uses three inline
CDN scripts (Tailwind play, Alpine.js, marked.js) for chrome and reads
its run-time data from a ``window.RUN_DATA`` JSON literal injected by
this module.

Static dashboard content (verdict, score, KPIs, judge reason summary,
health pills, run metadata) is rendered at build time via Jinja2 from
``run.json``. Interactive blocks (event timeline, artifact slide-over,
file preview drawer, tab switching) are Alpine.js bindings against
``window.RUN_DATA`` — which we assemble from ``run.json`` + the sibling
``__reports/<runId>/artifacts/`` and ``__reports/<runId>/inputs/`` dirs.

Tech_design §7.4 (modified 2026-05-30): the "no external CDN" Phase 1
constraint is relaxed — the report ships with 3 specific CDN scripts.
Offline use degrades to "no interactivity" but the Jinja2-rendered
content remains readable.
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


# ──────────────────────────────────────────────────────────────────────
# preprocessing helpers
# ──────────────────────────────────────────────────────────────────────

def _fmt_duration(ms: int | float | None) -> str:
    if ms is None:
        return "—"
    ms = int(ms)
    if ms < 1000:
        return f"{ms} ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s"
    m, s = divmod(ms // 1000, 60)
    return f"{m}:{s:02d}"


def _fmt_size(n: int | None) -> str:
    if n is None:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


def _fmt_cost(usd: float | None) -> str:
    if usd is None:
        return "—"
    return f"${usd:.2f}"


def _tool_calls_by_type(tool_calls: list[dict[str, Any]]) -> dict[str, int]:
    by: dict[str, int] = {}
    for tc in tool_calls or []:
        name = tc.get("name", "?")
        by[name] = by.get(name, 0) + 1
    return by


def _judge_skip_reason_human(reason: str, failed_ids: list[str] | None = None) -> str:
    """Human-readable text for the Judge headline when judge was skipped."""
    if reason == "provider_failed":
        return "Judge skipped (provider failed)."
    if reason == "blocking_assertion_failed":
        ids = failed_ids or []
        if ids:
            return f"Judge skipped (blocking assertion failed: {', '.join(ids)})."
        return "Judge skipped (blocking assertion failed)."
    return f"Judge skipped ({reason})." if reason else "Judge skipped."


def _split_criteria(criteria: str) -> list[str]:
    """Cheap parser: split combined rubric on lines starting with '- '."""
    out: list[str] = []
    for raw in (criteria or "").splitlines():
        line = raw.strip()
        if line.startswith("- "):
            out.append(line[2:].strip())
    return out


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _collect_files_under(root: Path) -> dict[str, str]:
    """Walk ``root`` and return ``{relative_path: text_content}``.

    Skips files we can't read as utf-8 (silently) so a binary leak
    doesn't break the report.
    """
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                out[str(p.relative_to(root))] = p.read_text(encoding="utf-8")
            except OSError:
                continue
            except UnicodeDecodeError:
                out[str(p.relative_to(root))] = f"<binary, {p.stat().st_size} B>"
    return out


# ──────────────────────────────────────────────────────────────────────
# the run.json → view dict + run-data dict pipeline
# ──────────────────────────────────────────────────────────────────────

def _build_run_data(run: dict[str, Any], report_dir: Path | None) -> dict[str, Any]:
    """Build the ``window.RUN_DATA`` payload (consumed by Alpine.js).

    Keys mirror the C4 demo's ``_data.js`` shape (camelCase). When
    ``report_dir`` is provided we also read the artifact contents and
    overlay/ground_truth files off disk; without it the report will
    still render but the slide-over panels will be empty.
    """
    artifacts = run.get("artifacts") or []
    art0 = artifacts[0] if artifacts else {}

    # the primary artifact's markdown body (for the slide-over preview)
    artifact_md = ""
    if report_dir is not None and art0.get("path"):
        artifact_md = _read_optional(report_dir / "artifacts" / art0["path"])

    # overlay + ground_truth file contents from __reports/<runId>/inputs/
    overlay_files: dict[str, str] = {}
    ground_truth: dict[str, str] = {}
    if report_dir is not None:
        overlay_files = _collect_files_under(report_dir / "inputs" / "overlay")
        ground_truth  = _collect_files_under(report_dir / "inputs" / "ground_truth")

    si = run.get("scenario_inputs") or {}
    judge = run.get("judge") or {}
    is_skipped = isinstance(judge, dict) and "skipped" in judge and "model" not in judge

    # criteriaList = parsed bullet items from the rubric
    criteria_list = [
        {"text": t} for t in _split_criteria(judge.get("criteria", "") if not is_skipped else "")
    ]

    # metaRows = key-value pairs rendered in the Meta tab
    requested_model = run.get("requested_model", "?")
    actual_model = run.get("actual_model") or requested_model
    meta_rows = [
        {"k": "run_id",          "v": run.get("run_id", "")},
        {"k": "git_commit",      "v": run.get("git_commit", "")},
        {"k": "timestamp",       "v": run.get("timestamp", "")},
        {"k": "cli_version",     "v": run.get("claude_cli_version", "")},
        {"k": "requested_model", "v": requested_model},
        {"k": "actual_model",    "v": actual_model},
        {"k": "model_drift",
         "v": "true" if run.get("model_drift") else "false",
         "cls": "text-amber-400" if run.get("model_drift") else "text-emerald-400"},
        {"k": "fixture_mode",    "v": run.get("fixture_mode", "")},
        {"k": "cwd",             "v": run.get("cwd", "")},
        {"k": "duration_ms",     "v": f"{run.get('duration_ms') or 0:,}".replace(",", " ")},
        {"k": "cost_usd",        "v": f"{run.get('cost_usd') or 0:.4f}"},
        {"k": "exit_code",       "v": str(run.get("exit_code", "?")),
         "cls": "text-emerald-400" if run.get("exit_code") == 0 else "text-rose-400"},
        {"k": "timeout",         "v": "true" if run.get("timeout") else "false"},
        {"k": "provider_status", "v": run.get("provider_status", "?"),
         "cls": "text-emerald-400" if run.get("provider_status") == "ok" else "text-rose-400"},
        {"k": "stderr_tail",     "v": run.get("stderr_tail") or "(empty)"},
        {"k": "overall",         "v": run.get("overall", "?"),
         "cls": "text-emerald-400 font-semibold" if run.get("overall") == "PASS"
                else "text-rose-400 font-semibold"},
    ]

    # artifactMetaRows = slide-over metadata for the primary artifact
    artifact_meta_rows: list[dict[str, Any]] = []
    if art0:
        sha = art0.get("sha256") or ""
        artifact_meta_rows = [
            {"k": "path",     "v": art0.get("path", "")},
            {"k": "size",     "v": f"{art0.get('size', 0):,} B ({_fmt_size(art0.get('size'))})".replace(",", " ")},
            {"k": "sha256",   "v": (sha[:16] + "…") if len(sha) > 16 else sha},
            {"k": "status",   "v": "NEW (written this run)",
             "cls": "text-emerald-400 font-semibold"},
            {"k": "mime",     "v": _guess_mime(art0.get("path", ""))},
            {"k": "abs path", "v": f"__reports/{run.get('run_id','?')}/artifacts/{art0.get('path','')}"},
        ]

    return {
        "artifactMarkdown": artifact_md,
        "artifactPath":     art0.get("path", ""),
        "artifactSize":     art0.get("size"),
        "artifactSha256":   art0.get("sha256", ""),
        "totalDurationMs":  run.get("duration_ms"),
        "events":           run.get("events") or [],
        "scenario": {
            "query":           si.get("query", ""),
            "description":     si.get("description", ""),
            "rubricDefault":   si.get("rubric_default", ""),
            "rubricAddition":  si.get("rubric_addition", ""),
            "provider":        si.get("provider") or {},
            "cwd":             run.get("cwd", ""),
            "fixtureMode":     run.get("fixture_mode", ""),
            "repeat":          (run.get("repeat") or {}).get("total", 1),
            "threshold":       run.get("threshold"),
        },
        "overlayFiles":     overlay_files,
        "groundTruth":      ground_truth,
        "criteriaList":     criteria_list,
        "overlayAdded":     run.get("overlay_added") or [],
        "metaRows":         meta_rows,
        "artifactMetaRows": artifact_meta_rows,
        # legacy fields kept so old c1/c2/c3 demos still load if pointed here
        "toolCalls":        run.get("tool_calls") or [],
        # Stage 2.3: pass the full baseline_diff payload to the client
        # so the Diff tab can render entirely from the data layer.
        "baselineDiff":     run.get("baseline_diff") or None,
        # Phase 2.6.B: assertions layer (Alpine renders the per-row table)
        "assertions":         run.get("assertions") or [],
        "assertionsSummary":  run.get("assertions_summary") or {},
        "judgeSkippedReason": (judge.get("skipped", "") if is_skipped else ""),
    }


_MIME_BY_EXT = {
    ".md": "text/markdown",
    ".html": "text/html",
    ".json": "application/json",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".txt": "text/plain",
}

def _guess_mime(path: str) -> str:
    for ext, mime in _MIME_BY_EXT.items():
        if path.lower().endswith(ext):
            return mime
    return "application/octet-stream"


def _build_view(run: dict[str, Any], report_dir: Path | None) -> dict[str, Any]:
    """Build the Jinja2 view dict (static dashboard content)."""
    judge = run.get("judge") or {}
    is_skipped = isinstance(judge, dict) and "skipped" in judge and "model" not in judge
    judge_skipped_reason = judge.get("skipped", "") if is_skipped else ""

    # Phase 2.6.B: assertion layer view fields
    assertions_list = run.get("assertions") or []
    assertions_summary = run.get("assertions_summary") or {}
    blocking_failed_ids: list[str] = (
        judge.get("failed_ids", []) if judge_skipped_reason == "blocking_assertion_failed"
        else [a["id"] for a in assertions_list
              if a.get("blocking") and a.get("status") != "pass"]
    )

    duration_ms = run.get("duration_ms") or 0
    score = float(judge.get("score") or 0.0)
    threshold = float(run.get("threshold") or 0.0)
    score_pct = max(0.0, min(1.0, score)) * 100

    tool_calls = run.get("tool_calls") or []
    by_type = _tool_calls_by_type(tool_calls)
    read_n  = by_type.get("Read", 0)
    bash_n  = by_type.get("Bash", 0)
    write_n = by_type.get("Write", 0)
    other_n = sum(v for k, v in by_type.items() if k not in ("Read", "Bash", "Write"))

    artifacts = run.get("artifacts") or []
    artifact_total = sum(int(a.get("size") or 0) for a in artifacts)

    criteria_list = _split_criteria(judge.get("criteria", "") if not is_skipped else "")

    si = run.get("scenario_inputs") or {}
    overlay_meta = si.get("overlay_files") or []
    gt_meta      = si.get("ground_truth_files") or []

    # Health checks split into 3 categories (matching C4 demo)
    health_blocking = [
        ("provider", run.get("provider_status", "?"), run.get("provider_status") == "ok"),
        ("exit", str(run.get("exit_code", "?")), run.get("exit_code") == 0),
        ("timeout", "true" if run.get("timeout") else "false", not run.get("timeout")),
    ]
    if run.get("stderr_tail"):
        health_blocking.append(("stderr", "present", False))
    else:
        health_blocking.append(("stderr", "empty", True))

    requested_model = run.get("requested_model", "?")
    actual_model    = run.get("actual_model") or requested_model
    health_drift = [
        ("drift", "none" if not run.get("model_drift") else "DRIFTED",
         not run.get("model_drift")),
        ("req → act", actual_model.split("-")[-1] if actual_model else "?", True),
        ("fixture", run.get("fixture_mode", "?"), True),
        ("+overlay", str(len(run.get("overlay_added") or [])), True),
        ("replaced", str(len(run.get("overlay_replaced") or [])), True),
    ]
    repeat = run.get("repeat") or {}
    health_stats = [
        ("repeat", f"{repeat.get('passed', 0)}/{repeat.get('total', 1)}"),
        ("pass-rate", f"{int(round(repeat.get('pass_rate', 0) * 100))}%"),
        ("cost", _fmt_cost(run.get("cost_usd"))),
        ("duration", _fmt_duration(duration_ms)),
        ("cli", run.get("claude_cli_version", "")),
    ]

    meta_rows = [
        ("run_id",          run.get("run_id", ""), ""),
        ("git_commit",      run.get("git_commit", ""), ""),
        ("timestamp",       run.get("timestamp", ""), ""),
        ("cli_version",     run.get("claude_cli_version", ""), ""),
        ("requested_model", requested_model, ""),
        ("actual_model",    actual_model, ""),
        ("model_drift",     "true" if run.get("model_drift") else "false",
         "text-amber-400" if run.get("model_drift") else "text-emerald-400"),
        ("fixture_mode",    run.get("fixture_mode", ""), ""),
        ("cwd",             run.get("cwd", ""), ""),
        ("duration_ms",     f"{duration_ms:,}".replace(",", " "), ""),
        ("cost_usd",        f"{run.get('cost_usd') or 0:.4f}", ""),
        ("exit_code",       str(run.get("exit_code", "?")),
         "text-emerald-400" if run.get("exit_code") == 0 else "text-rose-400"),
        ("timeout",         "true" if run.get("timeout") else "false", ""),
        ("provider_status", run.get("provider_status", "?"),
         "text-emerald-400" if run.get("provider_status") == "ok" else "text-rose-400"),
        ("overall",         run.get("overall", "?"),
         "text-emerald-400 font-semibold" if run.get("overall") == "PASS" else "text-rose-400 font-semibold"),
    ]

    # Stage 2.3: Diff tab visibility + summary badge
    bd = run.get("baseline_diff") or None
    diff_present     = bool(bd)
    diff_has_baseline = bool(bd and bd.get("has_baseline"))
    if diff_has_baseline:
        j = bd["judge"]
        a = bd["artifacts"]
        tc = bd["tool_calls"]
        ft = bd["final_text"]
        # human badge summary: e.g. "Δscore -0.03 · +1/-0 arts · 5→6 calls"
        score_delta = j["score_delta"]
        diff_badge_text = (
            ("Δ%+0.2f" % score_delta) if score_delta != 0 else "Δ=0"
        )
        # Simple PASS/CHANGED/REGRESS heuristic for the badge color
        if j["pass_flipped"] and not j["current_pass"]:
            diff_status = "regress"
        elif (a["added"] or a["removed"] or a["changed"]
              or ft["changed"] or tc["total_delta"] != 0
              or not tc["sequence_unchanged"]):
            diff_status = "changed"
        else:
            diff_status = "match"
        diff_warn_target_path = bool(
            bd["warnings"]["target_path_drift"]["drifted"]
        )
        diff_warn_model = bool(bd["warnings"]["model_drift"]["drifted"])
    elif diff_present:
        diff_badge_text = "no baseline"
        diff_status = "no-baseline"
        diff_warn_target_path = False
        diff_warn_model = False
    else:
        diff_badge_text = ""
        diff_status = ""
        diff_warn_target_path = False
        diff_warn_model = False

    return {
        "run_schema_version": run.get("run_schema_version", "1"),
        "skill":              run.get("skill", "?"),
        "scenario":           run.get("scenario", "?"),
        "run_id":             run.get("run_id", "?"),
        "overall":            run.get("overall", "?"),
        "overall_pass":       run.get("overall") == "PASS",
        "git_commit":         run.get("git_commit", ""),
        "cli_version":        run.get("claude_cli_version", ""),
        "timestamp":          run.get("timestamp", ""),
        "requested_model":    requested_model,
        "actual_model":       actual_model,
        "model_drift":        bool(run.get("model_drift")),
        "cwd":                run.get("cwd", ""),
        "duration_ms":        duration_ms,
        "duration_human":     _fmt_duration(duration_ms),
        "cost_usd":           run.get("cost_usd") or 0.0,
        "cost_human":         _fmt_cost(run.get("cost_usd")),
        "exit_code":          run.get("exit_code"),
        "provider_status":    run.get("provider_status", "ok"),
        "stderr_tail":        run.get("stderr_tail", ""),
        # judge
        "judge":              judge,
        "judge_skipped":      is_skipped,
        "judge_model":        judge.get("model", "?") if not is_skipped else "—",
        "judge_cached":       bool(judge.get("cached")) if not is_skipped else False,
        "judge_reason":       (
            judge.get("reason", "") if not is_skipped
            else _judge_skip_reason_human(judge_skipped_reason, blocking_failed_ids)
        ),
        "judge_skipped_reason": judge_skipped_reason,
        "judge_pass":         bool(judge.get("pass")) if not is_skipped else False,
        # Phase 2.6.B
        "assertions":              assertions_list,
        "assertions_summary":      assertions_summary,
        "assertions_total":        assertions_summary.get("total", 0),
        "assertions_passed":       assertions_summary.get("passed", 0),
        "assertions_failed":       assertions_summary.get("failed", 0),
        "assertions_errors":       assertions_summary.get("errors", 0),
        "assertions_blocking_failed": assertions_summary.get("blocking_failed", 0),
        "blocking_failed_ids":     blocking_failed_ids,
        "all_blocking_passed":     assertions_summary.get("all_blocking_passed", True),
        "criteria_list":      criteria_list,
        "rubric_text":        judge.get("criteria", "") if not is_skipped else "",
        # KPIs
        "score":              score,
        "score_pct":          score_pct,
        "score_overage":      f"+{score - threshold:.2f} over bar" if score > threshold else (
            f"{score - threshold:.2f} under bar"),
        "threshold":          threshold,
        # tool counts
        "tool_calls_count":   len(tool_calls),
        "read_n":             read_n,
        "bash_n":             bash_n,
        "write_n":            write_n,
        "other_n":            other_n,
        # artifacts
        "artifacts":          artifacts,
        "artifact_count":     len(artifacts),
        "artifact_total_human": _fmt_size(artifact_total),
        "deleted_count":      len(run.get("deleted_artifacts") or []),
        "overlay_replaced_count": len(run.get("overlay_replaced") or []),
        # primary artifact (for header + slide-over)
        "primary_artifact":   artifacts[0] if artifacts else None,
        "primary_artifact_short_sha": (artifacts[0].get("sha256") or "")[:8] if artifacts else "",
        "primary_artifact_size_human": _fmt_size(artifacts[0].get("size")) if artifacts else "—",
        # overlay (tab badge)
        "overlay_count":      len(overlay_meta),
        "overlay_added":      run.get("overlay_added") or [],
        # ground_truth (tab badge)
        "gt_count":           len(gt_meta),
        # events
        "events_count":       len(run.get("events") or []),
        # final_text
        "final_text":         run.get("final_text", ""),
        # health
        "health_blocking":    health_blocking,
        "health_drift":       health_drift,
        "health_stats":       health_stats,
        # repeat
        "repeat_total":       repeat.get("total", 1),
        "repeat_passed":      repeat.get("passed", 0),
        "pass_rate_pct":      int(round(repeat.get("pass_rate", 0) * 100)),
        # meta tab
        "meta_rows":          meta_rows,
        # Stage 2.3: Diff tab visibility + summary
        "diff_present":            diff_present,
        "diff_has_baseline":       diff_has_baseline,
        "diff_badge_text":         diff_badge_text,
        "diff_status":             diff_status,  # match / changed / regress / no-baseline
        "diff_warn_target_path":   diff_warn_target_path,
        "diff_warn_model":         diff_warn_model,
        "run_diff":                bd if diff_has_baseline else None,
        "current_target_path":     run.get("target_path", ""),
        # the run_data injected for Alpine
        "run_data_json":      json.dumps(_build_run_data(run, report_dir), ensure_ascii=False),
    }


# ──────────────────────────────────────────────────────────────────────
# public API (signatures unchanged for backward compat)
# ──────────────────────────────────────────────────────────────────────

def render(run: dict[str, Any], out_path: Path) -> None:
    """Render ``report.html`` next to ``out_path``."""
    out_path = Path(out_path)
    report_dir = out_path.parent
    view = _build_view(run, report_dir=report_dir)
    template = _ENV.get_template("report.html.j2")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template.render(**view), encoding="utf-8")


def write_run_json(run: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(run, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
