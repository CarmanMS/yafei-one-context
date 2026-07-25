"""Ground-truth schema + loader for ``onecxt eval judge-test``.

A ground-truth file lives at
``skills/<skill>/evals/<scenario>/ground_truth/<name>.yaml`` and
describes a hand-curated ``(final_text, artifacts)`` snapshot that a
human has already classified as ``pass`` or ``fail``. The judge-test
command feeds each ground truth through ``judge.evaluate`` (skipping the
real provider) and reports how often the judge agrees with the human
label — the matched-count is the rubric's calibration signal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class GroundTruthArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    content: str


class GroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected: Literal["pass", "fail"]
    final_text: str
    artifacts: list[GroundTruthArtifact] = []


def load_ground_truth(scenario_dir: Path) -> list[tuple[str, GroundTruth]]:
    """Load every ``*.yaml`` under ``<scenario_dir>/ground_truth/``.

    Returns a list of ``(name_without_ext, GroundTruth)`` tuples, sorted
    by file name so the output is deterministic across runs.

    Raises:
        FileNotFoundError: when the ``ground_truth/`` directory is missing.
        pydantic.ValidationError: when any file fails schema validation
            (propagated so callers can surface a precise error).
    """
    gt_dir = scenario_dir / "ground_truth"
    if not gt_dir.is_dir():
        raise FileNotFoundError(f"ground_truth dir missing: {gt_dir}")

    out: list[tuple[str, GroundTruth]] = []
    for p in sorted(gt_dir.glob("*.yaml")):
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{p}: expected a YAML mapping at top level")
        gt = GroundTruth.model_validate(raw)
        out.append((p.stem, gt))
    return out
