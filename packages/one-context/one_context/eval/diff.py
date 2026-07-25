"""Compute a baseline-vs-current diff (Stage 2.2).

Consumed by the runner when ``--diff`` is set; the result is
embedded into ``run.json`` under ``baseline_diff`` and rendered
into the HTML report by a dedicated "Diff" tab (Stage 2.3).

Diff dimensions (plan §Stage 2.2):
  - judge score delta + pass flip
  - tool_calls sequence (by-type counts + total)
  - artifacts ± (added / removed / sha256-changed)
  - final_text unified diff
  - actual_model drift (warn)
  - target_path_sha256 drift vs ``target_path_sha256_at_snapshot``
    (warn — input feature was changed since the baseline was taken)

The runner is responsible for passing in a parsed baseline.json
dict (or None when no baseline exists yet). When None, the diff
result has ``has_baseline = False`` and all other fields are
empty / zero — callers can still render a "no baseline yet" view.
"""

from __future__ import annotations

import difflib
from collections import Counter
from typing import Any


def _tool_type_sequence(tool_calls: list[dict[str, Any]]) -> list[str]:
    return [str(c.get("type") or c.get("name") or "?") for c in tool_calls]


def _tool_type_counts(tool_calls: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(_tool_type_sequence(tool_calls)))


def _artifacts_index(run: dict) -> dict[str, dict]:
    """Build {path -> {size, sha256}} from a run dict."""
    out: dict[str, dict] = {}
    for a in run.get("artifacts") or []:
        path = a.get("path")
        if not path:
            continue
        out[path] = {
            "size":   int(a.get("size") or 0),
            "sha256": str(a.get("sha256") or ""),
        }
    return out


def _final_text_unified(
    baseline_text: str, current_text: str, *, context: int = 3,
) -> str:
    """Return a unified diff string; empty when the two are identical."""
    if baseline_text == current_text:
        return ""
    return "".join(difflib.unified_diff(
        baseline_text.splitlines(keepends=True),
        current_text.splitlines(keepends=True),
        fromfile="baseline/final_text",
        tofile="current/final_text",
        n=context,
    ))


def compute(
    *,
    current_run: dict,
    baseline_run: dict | None,
) -> dict[str, Any]:
    """Compute a serializable diff dict.

    When ``baseline_run`` is None (no snapshot yet), returns
    ``{"has_baseline": False, "note": "..."}``.
    """
    if baseline_run is None:
        return {
            "has_baseline": False,
            "note": "no baseline snapshot exists; run `onecxt eval "
                    "<skill>/<scenario> snapshot --reason \"…\"` first",
        }

    # ── header / provenance ───────────────────────────────────────
    b_judge = baseline_run.get("judge") or {}
    c_judge = current_run.get("judge") or {}
    b_score = float(b_judge.get("score") or 0.0)
    c_score = float(c_judge.get("score") or 0.0)
    b_pass  = bool(b_judge.get("pass"))
    c_pass  = bool(c_judge.get("pass"))

    # ── tool_calls ────────────────────────────────────────────────
    b_seq = _tool_type_sequence(baseline_run.get("tool_calls") or [])
    c_seq = _tool_type_sequence(current_run.get("tool_calls") or [])
    b_counts = _tool_type_counts(baseline_run.get("tool_calls") or [])
    c_counts = _tool_type_counts(current_run.get("tool_calls") or [])
    all_types = sorted(set(b_counts) | set(c_counts))
    by_type_delta = {
        t: c_counts.get(t, 0) - b_counts.get(t, 0)
        for t in all_types
        if c_counts.get(t, 0) - b_counts.get(t, 0) != 0
    }

    # ── artifacts ─────────────────────────────────────────────────
    b_arts = _artifacts_index(baseline_run)
    c_arts = _artifacts_index(current_run)
    added   = sorted(set(c_arts) - set(b_arts))
    removed = sorted(set(b_arts) - set(c_arts))
    changed: list[dict[str, Any]] = []
    for path in sorted(set(b_arts) & set(c_arts)):
        if b_arts[path]["sha256"] != c_arts[path]["sha256"]:
            changed.append({
                "path":            path,
                "baseline_size":   b_arts[path]["size"],
                "current_size":    c_arts[path]["size"],
                "baseline_sha256": b_arts[path]["sha256"],
                "current_sha256":  c_arts[path]["sha256"],
            })

    # ── final_text ────────────────────────────────────────────────
    b_text = baseline_run.get("final_text") or ""
    c_text = current_run.get("final_text") or ""
    final_text_diff = _final_text_unified(b_text, c_text)

    # ── warnings ──────────────────────────────────────────────────
    b_model = baseline_run.get("actual_model") or baseline_run.get("requested_model") or ""
    c_model = current_run.get("actual_model") or current_run.get("requested_model") or ""
    model_drift = bool(b_model) and bool(c_model) and b_model != c_model

    target_path_sha_at_snap = (
        baseline_run.get("target_path_sha256_at_snapshot")
        or baseline_run.get("target_path_sha256")
        or ""
    )
    cur_target_path_sha = current_run.get("target_path_sha256") or ""
    target_path_drift = (
        bool(target_path_sha_at_snap)
        and bool(cur_target_path_sha)
        and target_path_sha_at_snap != cur_target_path_sha
    )

    return {
        "has_baseline": True,
        "baseline": {
            "run_id":            baseline_run.get("snapshot_run_id")
                                 or baseline_run.get("run_id"),
            "snapshot_at":       baseline_run.get("snapshot_at", ""),
            "snapshot_reason":   baseline_run.get("snapshot_reason", ""),
            "target_path_sha256_at_snapshot": target_path_sha_at_snap,
        },
        "current": {
            "run_id":             current_run.get("run_id"),
            "target_path_sha256": cur_target_path_sha,
        },
        "judge": {
            "baseline_score": b_score,
            "current_score":  c_score,
            "score_delta":    round(c_score - b_score, 4),
            "baseline_pass":  b_pass,
            "current_pass":   c_pass,
            "pass_flipped":   b_pass != c_pass,
        },
        "tool_calls": {
            "baseline_total": len(b_seq),
            "current_total":  len(c_seq),
            "total_delta":    len(c_seq) - len(b_seq),
            "sequence_unchanged": b_seq == c_seq,
            "by_type_delta":  by_type_delta,
            "baseline_by_type": b_counts,
            "current_by_type":  c_counts,
        },
        "artifacts": {
            "added":   added,
            "removed": removed,
            "changed": changed,
            "unchanged_count": len(set(b_arts) & set(c_arts)) - len(changed),
        },
        "final_text": {
            "changed":       bool(final_text_diff),
            "baseline_size": len(b_text),
            "current_size":  len(c_text),
            "unified_diff":  final_text_diff,
        },
        "warnings": {
            "model_drift": {
                "drifted":        model_drift,
                "baseline_model": b_model,
                "current_model":  c_model,
            },
            "target_path_drift": {
                "drifted":                       target_path_drift,
                "baseline_sha256_at_snapshot":   target_path_sha_at_snap,
                "current_sha256":                cur_target_path_sha,
            },
        },
    }


def load_baseline(scenario_dir) -> dict | None:
    """Load ``__baselines/baseline.json`` if present, else None."""
    import json
    from pathlib import Path
    p = Path(scenario_dir) / "__baselines" / "baseline.json"
    if not p.is_file():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
