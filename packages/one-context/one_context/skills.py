"""Discover and parse skills from the ``skills/`` directory.

Each skill lives in ``skills/<name>/SKILL.md`` with optional YAML
frontmatter.  This module scans the directory, parses frontmatter,
and returns structured ``SkillMeta`` objects used by adapters to
generate tool-specific registration files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Runtime install / uninstall helpers for Claude Code Skill tool
# ---------------------------------------------------------------------------

@dataclass
class InstallResult:
    """Outcome of a batch skill install operation."""

    installed: list[str]
    skipped: list[str]
    errors: list[str]


@dataclass
class UninstallResult:
    """Outcome of a batch skill uninstall operation."""

    removed: list[str]
    skipped: list[str]


def _claude_skills_home() -> Path:
    """Return the Claude Code runtime skills directory."""
    return Path.home() / ".claude" / "skills"


def install_skills(root: Path, names: list[str]) -> InstallResult:
    """Copy project ``skills/<name>/SKILL.md`` into ``~/.claude/skills/<name>/``.

    Only copies when the target does not already exist; existing files are
    reported as *skipped* so callers can decide whether to force overwrite.
    """
    installed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    dest_root = _claude_skills_home()

    for name in names:
        src = root / "skills" / name / "SKILL.md"
        if not src.is_file():
            errors.append(f"{name}: not found in skills/{name}/SKILL.md")
            continue

        dest_dir = dest_root / name
        dest = dest_dir / "SKILL.md"
        if dest.is_file():
            skipped.append(name)
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        installed.append(name)

    return InstallResult(installed=installed, skipped=skipped, errors=errors)


def uninstall_skills(names: list[str]) -> UninstallResult:
    """Remove ``~/.claude/skills/<name>/`` directories.

    Directories that do not exist are reported as *skipped*.
    """
    import shutil

    removed: list[str] = []
    skipped: list[str] = []
    dest_root = _claude_skills_home()

    for name in names:
        dest_dir = dest_root / name
        if not dest_dir.exists():
            skipped.append(name)
            continue

        shutil.rmtree(dest_dir)
        removed.append(name)

    return UninstallResult(removed=removed, skipped=skipped)


def list_skills_install_status(root: Path) -> dict[str, Any]:
    """Return project skills and their Claude Code runtime installation status."""
    project = [s.dir_name for s in discover_skills(root)]
    dest_root = _claude_skills_home()
    installed = sorted(
        d.name for d in dest_root.iterdir() if d.is_dir()
    ) if dest_root.is_dir() else []
    return {"project": project, "installed": installed}


# ---------------------------------------------------------------------------
# SkillMeta & parsing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillMeta:
    """Parsed representation of a single ``SKILL.md``.

    Attributes
    ----------
    name:
        Human-readable skill name from frontmatter (falls back to
        directory name when absent).
    dir_name:
        Directory name under ``skills/``, e.g. ``smart-commit``.
        Used as the stable unique identifier.
    frontmatter:
        Raw parsed YAML frontmatter dict (empty ``{}`` when no
        frontmatter is present).
    body:
        Markdown body after the closing ``---`` of frontmatter.
    source_path:
        Relative path such as ``skills/smart-commit/SKILL.md``.
    source_dir:
        Relative path such as ``skills/smart-commit/``.
    """

    name: str
    dir_name: str
    frontmatter: dict[str, Any]
    body: str
    source_path: str
    source_dir: str


def discover_skills(root: Path) -> list[SkillMeta]:
    """Scan ``root/skills/`` for ``SKILL.md`` files and parse them.

    Returns an empty list when the ``skills/`` directory does not
    exist.  Results are sorted by directory name for deterministic
    output across runs.
    """
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []

    result: list[SkillMeta] = []
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        meta = parse_skill_md(root, skill_md)
        if meta is not None:
            result.append(meta)
    return result


def parse_skill_md(root: Path, skill_md: Path) -> SkillMeta | None:
    """Parse a single ``SKILL.md``: extract YAML frontmatter + body.

    Returns ``None`` only if the file cannot be read.
    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    dir_name = skill_md.parent.name
    source_path = skill_md.relative_to(root).as_posix()
    source_dir = skill_md.parent.relative_to(root).as_posix() + "/"

    if not text.startswith("---"):
        # No frontmatter — use entire text as body
        return SkillMeta(
            name=dir_name,
            dir_name=dir_name,
            frontmatter={},
            body=text.strip(),
            source_path=source_path,
            source_dir=source_dir,
        )

    # Find closing ---
    end = text.find("---", 3)
    if end == -1:
        # Unclosed frontmatter — treat entire text as body
        return SkillMeta(
            name=dir_name,
            dir_name=dir_name,
            frontmatter={},
            body=text.strip(),
            source_path=source_path,
            source_dir=source_dir,
        )

    fm_text = text[3:end].strip()
    body = text[end + 3 :].strip()

    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}

    if not isinstance(fm, dict):
        fm = {}

    name = fm.get("name") or dir_name

    return SkillMeta(
        name=name,
        dir_name=dir_name,
        frontmatter=fm,
        body=body,
        source_path=source_path,
        source_dir=source_dir,
    )


def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from a markdown string.

    If the string starts with ``---``, everything up to and including
    the second ``---`` is stripped.  Otherwise the text is returned
    unchanged.
    """
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3 :].strip()


def resolve_skill_body(root: Path, skill: SkillMeta) -> str:
    """Return the body of a skill, reading from disk when possible.

    Adapters that need to *inline* skill content should use this helper
    instead of manually reading ``skills/<name>/SKILL.md`` and stripping
    frontmatter.  It centralises the fallback logic (disk → cached meta)
    and guarantees identical behaviour across all adapters.

    Parameters
    ----------
    root:
        Project root (containing ``skills/``).
    skill:
        Parsed metadata from ``discover_skills``.

    Returns
    -------
    str
        Frontmatter-stripped SKILL.md body.
    """
    skill_path = root / skill.source_path
    if skill_path.is_file():
        return strip_frontmatter(skill_path.read_text(encoding="utf-8"))
    # Fallback to the already-parsed body stored in SkillMeta
    return skill.body