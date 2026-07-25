"""Pydantic schema for `skills/<name>/eval.yaml`.

skill-level config:
- description (optional)
- judge_model (default haiku)
- artifacts: list of glob patterns relative to scenario.cwd
- default_rubric: free-form natural-language rubric, can be overridden
  per scenario.
- assertions: declarative pre-judge checks (Phase 2.6.B). The skill list
  is the baseline; scenarios can add more or call `assertions_skip` to
  reverse-disable a default by id. See `one_context.eval.assertions` for
  the DSL spec.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from one_context.eval.assertions import AssertionSpec
from one_context.eval.judge import DEFAULT_JUDGE_MODEL


class SkillEvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = ""
    judge_model: str = DEFAULT_JUDGE_MODEL
    artifacts: list[str] = Field(default_factory=list)
    default_rubric: str = ""
    assertions: list[AssertionSpec] = Field(default_factory=list)


def load_skill_eval(skill_dir: Path) -> SkillEvalConfig:
    """Load `<skill_dir>/eval.yaml` (returns defaults if missing)."""
    path = skill_dir / "eval.yaml"
    if not path.is_file():
        return SkillEvalConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping at top level")
    return SkillEvalConfig.model_validate(raw)
