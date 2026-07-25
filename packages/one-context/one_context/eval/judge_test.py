"""`onecxt eval judge-test <skill>/<scenario>` — judge calibration loop.

Feeds every ``ground_truth/*.yaml`` to ``judge.evaluate`` without spawning
the real provider. Reports per-file agreement and a final ``matched/total``
score. ANSI green when ≥3/4, red when ≤2/4 (matches the calibration
gate in implementation_plan Stage 1.3.6 / Phase 1 退出条件).
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from one_context.eval import judge as judge_mod
from one_context.eval.ground_truth import GroundTruth, load_ground_truth
from one_context.eval.skill_config import load_skill_eval
from one_context.eval.scenario_config import load_scenario


# Pass/fail decision threshold for a ground truth: judge_res.pass_ value.
# Per Stage 1.1.9 spec: judge_res.pass_=True ↔ expected="pass"; vice versa.
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


@dataclass
class JudgeTestRow:
    name: str
    expected: str  # "pass" | "fail"
    actual: str  # "pass" | "fail"
    matched: bool
    score: float
    reason: str


def _resolve(repo_root: Path, target: str) -> tuple[str, str, Path, Path]:
    if "/" not in target:
        raise ValueError(f"expected '<skill>/<scenario>', got: {target!r}")
    skill, scenario = target.split("/", 1)
    if not skill or not scenario or "/" in scenario:
        raise ValueError(f"invalid skill/scenario: {target!r}")
    skill_dir = repo_root / "skills" / skill
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"skill dir missing: {skill_dir}")
    scenario_dir = skill_dir / "evals" / scenario
    if not scenario_dir.is_dir():
        raise FileNotFoundError(f"scenario dir missing: {scenario_dir}")
    return skill, scenario, skill_dir, scenario_dir


def _artifacts_for_judge(gt: GroundTruth) -> list[dict]:
    """Convert ground-truth artifacts → judge.evaluate input shape."""
    out: list[dict] = []
    for art in gt.artifacts:
        content = art.content or ""
        data = content.encode("utf-8")
        out.append({
            "path": art.path,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "head": content[:4096],
        })
    return out


def _trunc(s: str, n: int = 80) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _row_match_mark(matched: bool) -> str:
    return "PASS" if matched else "FAIL"


def run_judge_test(
    *,
    repo_root: Path,
    target: str,
    out: TextIO | None = None,
    color: bool | None = None,
) -> tuple[list[JudgeTestRow], int, int]:
    """Run judge-test for ``<skill>/<scenario>``.

    Returns ``(rows, matched, total)``. Caller picks the exit code.
    """
    if out is None:
        out = sys.stdout
    if color is None:
        color = out.isatty()

    skill, scenario, skill_dir, scenario_dir = _resolve(repo_root, target)
    skill_cfg = load_skill_eval(skill_dir)
    scen_cfg = load_scenario(scenario_dir)
    criteria = judge_mod.merge_rubric(skill_cfg.default_rubric, scen_cfg.rubric)
    if not criteria.strip():
        raise ValueError(
            f"no rubric configured for {target} — set skills/<skill>/eval.yaml "
            f"default_rubric or scenario.yaml rubric"
        )

    gts = load_ground_truth(scenario_dir)
    if not gts:
        raise FileNotFoundError(
            f"no ground_truth/*.yaml found in {scenario_dir / 'ground_truth'}"
        )

    # Stage 2.X.5 alignment: judge always uses the provider's effective model
    # (resolved from settings.json), not skill_cfg.judge_model. judge-test must
    # match — otherwise it spawns claude with a model name the gateway rejects.
    from one_context.eval.judge import _resolve_settings_path
    from one_context.eval.settings_resolver import (
        ModelResolveError,
        resolve_effective_model,
    )
    try:
        resolved = resolve_effective_model(
            yaml_model=scen_cfg.provider.model,
            settings_path=_resolve_settings_path(),
        )
        effective_model = resolved.model
    except ModelResolveError as e:
        raise ValueError(f"cannot resolve judge model: {e}") from e

    rows: list[JudgeTestRow] = []
    # judge-cache: scoped to a tmpdir so we don't pollute the scenario's
    # real __reports/<runId>/judge-cache/ during calibration runs.
    with tempfile.TemporaryDirectory(prefix="onecxt-judge-test-") as td:
        cache_dir = Path(td)
        for name, gt in gts:
            artifacts = _artifacts_for_judge(gt)
            judge_res = judge_mod.evaluate(
                criteria=criteria,
                final_text=gt.final_text,
                tool_calls=[],
                artifacts=artifacts,
                cache_dir=cache_dir,
                model=effective_model,
            )
            actual = "pass" if judge_res.pass_ else "fail"
            matched = (actual == gt.expected)
            rows.append(JudgeTestRow(
                name=name,
                expected=gt.expected,
                actual=actual,
                matched=matched,
                score=judge_res.score,
                reason=judge_res.reason,
            ))

    # ----- format the comparison table -----
    name_w = max(len("ground_truth name"), *(len(r.name) for r in rows))
    name_w = min(name_w, 40)
    header = (
        f"{'ground_truth name'.ljust(name_w)} | expected | actual judge | match | score | judge reason (前 80 字)"
    )
    sep = "-" * name_w + "-+----------+--------------+-------+-------+" + "-" * 24
    out.write(header + "\n")
    out.write(sep + "\n")
    for r in rows:
        mark = _row_match_mark(r.matched)
        out.write(
            f"{r.name[:name_w].ljust(name_w)} | "
            f"{r.expected.ljust(8)} | "
            f"{r.actual.ljust(12)} | "
            f"{mark.ljust(5)} | "
            f"{r.score:>5.2f} | "
            f"{_trunc(r.reason)}\n"
        )

    matched = sum(1 for r in rows if r.matched)
    total = len(rows)
    out.write("\n")
    verdict_text = f"吻合度：{matched}/{total} PASS"
    if matched >= 3 and total >= 4:
        msg = f"JUDGE 可用 ({verdict_text})"
        out.write(f"{GREEN}{msg}{RESET}\n" if color else msg + "\n")
    elif total < 4:
        out.write(
            f"{verdict_text} — 警告：ground_truth 样本不足 4 份，无法套用 ≥3/4 标准\n"
        )
    else:
        msg = f"JUDGE 不可用，回 rubric 调 ({verdict_text})"
        out.write(f"{RED}{msg}{RESET}\n" if color else msg + "\n")

    return rows, matched, total
