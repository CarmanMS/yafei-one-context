"""Prompt template loader for the recorder package (Phase 2.8 M3).

All recorder LLM prompts live as `*.md` files under this package
directory so they ship with the wheel via `setuptools.packages.find`
(any subpackage's `*.md` siblings are picked up alongside `.py`).

Loader contract:

- `load_prompt(name)` returns the raw markdown text for
  `<this_dir>/<name>`. Path arg may include `/` to descend into
  subdirectories (e.g. `negative_cases/_default.md`).
- `render_prompt(name, **vars)` is a thin Jinja2 wrapper using
  `StrictUndefined` so a missing variable surfaces immediately rather
  than rendering as empty (silent-empty makes prompt regressions hard
  to diagnose).
- `load_negative_case_library(skill_name, repo_root)` looks up the
  per-skill false-positive reference library. Skills own their library:
  `<repo_root>/skills/<skill>/evals/_negative_cases.md`. The framework
  ships only `negative_cases/_default.md` as a generic fallback so
  finalize never crashes on unknown skills.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jinja2 import Environment, StrictUndefined

_PROMPTS_DIR = Path(__file__).parent


def _env() -> Environment:
    # Recorder prompts are markdown templates, not HTML — no autoescape.
    return Environment(
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def load_prompt(name: str) -> str:
    """Return raw markdown for `<prompts_dir>/<name>`."""
    path = _PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"recorder prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **vars: object) -> str:
    """Jinja2-render a prompt template against `vars`."""
    tpl = _env().from_string(load_prompt(name))
    return tpl.render(**vars)


def _find_skill_dir(skill_name: str, start: Path) -> Optional[Path]:
    """Walk upward from `start` looking for `skills/<skill>/SKILL.md`.

    The MCP server's working directory is whatever cwd the parent cc was
    in when it spawned the server — often a sub-directory of the repo
    (e.g. `packages/one-context`), not the repo root. A naive
    `Path.cwd() / 'skills' / skill_name` therefore misses the file.
    Walking up to the first ancestor whose `skills/<skill>/SKILL.md`
    exists makes loader resolution independent of cwd.
    """
    current = start.resolve()
    for ancestor in (current, *current.parents):
        candidate = ancestor / "skills" / skill_name / "SKILL.md"
        if candidate.is_file():
            return candidate.parent
    return None


def load_negative_case_library(
    skill_name: str,
    repo_root: Optional[Path] = None,
) -> str:
    """Return the per-skill false-positive reference library.

    Resolution order:
    1. Skill-owned: `<skill_dir>/evals/_negative_cases.md`, where
       `<skill_dir>` is found by walking up from `repo_root` (or
       `Path.cwd()` when None) to the first ancestor containing
       `skills/<skill>/SKILL.md`. Reflects that the reverse-spec of a
       skill belongs to the skill, not the framework.
    2. Framework fallback: `negative_cases/_default.md` shipped with the
       recorder package — used when the skill has no curated library so
       finalize still has a generic template to anchor F-NN structure.
    """
    start = Path(repo_root) if repo_root is not None else Path.cwd()
    skill_dir = _find_skill_dir(skill_name, start)
    if skill_dir is not None:
        skill_lib = skill_dir / "evals" / "_negative_cases.md"
        if skill_lib.is_file():
            return skill_lib.read_text(encoding="utf-8")

    try:
        return load_prompt("negative_cases/_default.md")
    except FileNotFoundError:
        return "(no negative-case library available)"


__all__ = [
    "load_prompt",
    "render_prompt",
    "load_negative_case_library",
]
