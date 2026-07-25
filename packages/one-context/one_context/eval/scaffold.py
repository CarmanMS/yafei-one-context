"""Generate a minimal scenario scaffold (Stage 2.4).

Used by ``onecxt eval init <skill>/<scenario>`` to bootstrap a new
scenario with sensible defaults. We deliberately keep the template
small — just enough to run + judge, with TODO markers so the author
can't forget to fill in the rubric.

Layout produced under ``skills/<skill>/evals/<scenario>/``:

    scenario.yaml                 # description / target_path / query / rubric / threshold
    ground_truth/pass-01.yaml     # one passing sample (for judge-test)
    ground_truth/fail-01.yaml     # one failing sample (for judge-test)

We do NOT touch ``skills/<skill>/eval.yaml`` — that's a skill-level
concern (artifacts globs + default_rubric + judge_model) and the
author may already have one. We warn when it's missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SCENARIO_TEMPLATE = """\
# Created by `onecxt eval init {skill}/{scenario}` — fill in TODOs below.

description: |
  TODO: one paragraph describing what this scenario exercises.

# Path (relative to repo root) into which the agent should operate.
# Use the shared evaluation fixture pool under features/_evals/.
target_path: features/_evals/TODO-category/TODO-feature-content-ready/

query: |
  TODO: the user query passed to claude -p.
  Use {{{{ target_path }}}} interpolation to reference files under the fixture.

provider:
  # `model` is intentionally omitted — runner resolves it at runtime from
  # $ONECXT_CLAUDE_SETTINGS' env.ANTHROPIC_MODEL. Set `model:` here only
  # to pin a different model for this scenario.
  permissionMode: bypassPermissions
  timeoutMs: 300000

repeat: 1
threshold: 0.8

rubric: |
  TODO: scenario-specific rubric additions (the skill-level default
  rubric in eval.yaml is automatically merged in front of this text).
  Write 3-6 specific, testable criteria — concrete enough that an
  LLM judge can produce a stable PASS/FAIL on a re-run.
"""


GT_PASS_TEMPLATE = """\
# PASS sample — the model output that a healthy run should produce.
# Used by `onecxt eval judge-test {skill}/{scenario}` for rubric
# calibration (does the judge agree this should pass?).

expected: pass

final_text: |
  TODO: a representative final_text that satisfies every rubric criterion.

artifacts:
  - path: TODO/relative/to/target_path.md
    content: |
      TODO: a representative artifact body the agent should write.
"""


GT_FAIL_TEMPLATE = """\
# FAIL sample — the model output that a regression should produce.
# Used by `onecxt eval judge-test {skill}/{scenario}` for rubric
# calibration (does the judge correctly mark this as failing?).

expected: fail

final_text: |
  TODO: a final_text that *misses* one or more rubric criteria —
  describe what's wrong / missing so the judge has something to bite on.

artifacts:
  - path: TODO/relative/to/target_path.md
    content: |
      TODO: an artifact body that violates the rubric on purpose
      (wrong structure, missing required section, wrong format, etc.)
"""


@dataclass
class InitOutcome:
    scenario_dir: Path
    files_created: list[Path]
    warnings: list[str]


class InitError(Exception):
    """Init refused — scenario already exists, skill missing, etc."""


def init_scenario(
    *,
    repo_root: Path,
    skill: str,
    scenario: str,
) -> InitOutcome:
    """Create scenario.yaml + ground_truth/{pass,fail}-01.yaml.

    Raises:
        InitError: skill dir missing, scenario.yaml already exists.
    """
    skill_dir = repo_root / "skills" / skill
    if not skill_dir.is_dir():
        raise InitError(f"skill dir missing: {skill_dir}")

    scn_dir = skill_dir / "evals" / scenario
    if (scn_dir / "scenario.yaml").is_file():
        raise InitError(
            f"scenario.yaml already exists at {scn_dir / 'scenario.yaml'}; "
            "refusing to overwrite"
        )

    gt_dir = scn_dir / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    scn_yaml = scn_dir / "scenario.yaml"
    scn_yaml.write_text(
        SCENARIO_TEMPLATE.format(skill=skill, scenario=scenario),
        encoding="utf-8",
    )
    files.append(scn_yaml)

    pass_gt = gt_dir / "pass-01.yaml"
    pass_gt.write_text(
        GT_PASS_TEMPLATE.format(skill=skill, scenario=scenario),
        encoding="utf-8",
    )
    files.append(pass_gt)

    fail_gt = gt_dir / "fail-01.yaml"
    fail_gt.write_text(
        GT_FAIL_TEMPLATE.format(skill=skill, scenario=scenario),
        encoding="utf-8",
    )
    files.append(fail_gt)

    warnings: list[str] = []
    if not (skill_dir / "eval.yaml").is_file():
        warnings.append(
            f"skill-level eval.yaml missing at {skill_dir / 'eval.yaml'}; "
            "create one with `artifacts` globs + `default_rubric` + "
            "`judge_model` before running this scenario"
        )

    return InitOutcome(
        scenario_dir=scn_dir,
        files_created=files,
        warnings=warnings,
    )
