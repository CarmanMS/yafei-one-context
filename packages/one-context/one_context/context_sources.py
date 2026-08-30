"""Safety boundary for manifest-provided context paths."""

from __future__ import annotations

from pathlib import Path


def resolve_context_source(root: Path, raw: str) -> tuple[Path, Path]:
    """Resolve a context source without exposing the Obsidian vault or parent paths."""
    rel = Path(raw.strip())
    if not rel.parts or rel.is_absolute():
        raise ValueError("context paths must be relative to the one-context root")
    if rel.parts[0].casefold() == "knowledge":
        raise ValueError(
            "knowledge/** is API-only; load skills/obsidian-knowledge/SKILL.md instead"
        )

    root_resolved = root.resolve()
    target = (root_resolved / rel).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("context paths may not escape the one-context root") from exc
    return rel, target
