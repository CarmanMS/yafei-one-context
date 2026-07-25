"""Phase 2.6.B: load every real `skills/<name>/eval.yaml` + each scenario.yaml
and verify the new `assertions:` field parses cleanly.

This test guards against typos in the YAML (e.g. unknown kind, bad
field name caught by `extra=forbid`) without depending on Claude CLI.
It does NOT validate semantics — that requires running the full eval.

Lives in the package tests so it runs in CI alongside everything else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from one_context.eval.assertions import AssertionSpec, merge_assertions
from one_context.eval.scenario_config import load_scenario
from one_context.eval.skill_config import load_skill_eval


REPO_ROOT = Path(__file__).resolve().parents[4]


def _all_scenarios() -> list[tuple[str, Path, Path]]:
    """Yield (skill_id, skill_dir, scenario_dir) for every scenario in the repo."""
    skills_dir = REPO_ROOT / "skills"
    out: list[tuple[str, Path, Path]] = []
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        evals = skill / "evals"
        if not evals.is_dir():
            continue
        for scn in sorted(p for p in evals.iterdir() if p.is_dir()):
            if (scn / "scenario.yaml").is_file():
                out.append((skill.name, skill, scn))
    return out


# ---------------------------------------------------------------------------
# Per-skill: eval.yaml parses + every assertion has an id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skill_id",
    ["cover-prompt", "info-radar", "remotion-pipelines"],
)
def test_skill_eval_yaml_loads_with_assertions(skill_id: str):
    skill_dir = REPO_ROOT / "skills" / skill_id
    cfg = load_skill_eval(skill_dir)

    # Every assertion must have a non-empty id (required for skip + collision)
    seen: set[str] = set()
    for a in cfg.assertions:
        assert isinstance(a, AssertionSpec)
        assert a.id and a.id.strip(), f"{skill_id}: assertion missing id: {a}"
        assert a.id not in seen, f"{skill_id}: duplicate assertion id within skill: {a.id}"
        seen.add(a.id)


# ---------------------------------------------------------------------------
# Per-scenario: scenario.yaml parses + assertions merge cleanly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skill_id,scenario_id",
    [
        (s_id, scn.name)
        for s_id, _, scn in _all_scenarios()
        if s_id in {"cover-prompt", "info-radar", "remotion-pipelines"}
    ],
)
def test_scenario_yaml_loads_and_merges(skill_id: str, scenario_id: str):
    skill_dir = REPO_ROOT / "skills" / skill_id
    scn_dir = skill_dir / "evals" / scenario_id
    skill_cfg = load_skill_eval(skill_dir)
    scn_cfg = load_scenario(scn_dir)

    # Scenario assertions also need ids
    for a in scn_cfg.assertions:
        assert a.id and a.id.strip(), (
            f"{skill_id}/{scenario_id}: scenario assertion missing id: {a}"
        )

    # Merge MUST succeed (no id collision without explicit skip).
    merged = merge_assertions(
        skill_cfg.assertions, scn_cfg.assertions, scn_cfg.assertions_skip,
    )
    # Sanity: no duplicate ids in the merged list either
    ids = [a.id for a in merged]
    assert len(ids) == len(set(ids)), (
        f"{skill_id}/{scenario_id}: merged assertion ids contain duplicates: {ids}"
    )
