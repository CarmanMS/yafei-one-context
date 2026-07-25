"""Artifact collection via sha256 pre/post snapshot.

Per ISS-015: spawn-pre and spawn-post we sha256 every file matched by the
artifact glob whitelist; the produced artifacts are
    (new paths) ∪ (paths whose sha256 changed)
plus a separately-recorded list of deleted paths.

We deliberately do NOT use mtime / `find -newer` — that approach silently
fails when (a) a skill writes via `cp -p` / `shutil.copy2` (which
preserves source mtime) or (b) the marker and the artifact land in the
same fs-second on coarse-grained filesystems (ext4, HFS+).
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileSnapshot:
    rel_path: str
    sha256: str
    size: int


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _glob_relative(base: Path, patterns: list[str]) -> list[Path]:
    """Resolve every glob pattern relative to base, return existing files.

    Patterns are forward-slash, relative to `base`. We use `Path.glob`
    so `**` works. Results are de-duplicated and sorted.
    """
    seen: dict[Path, None] = {}
    for pat in patterns:
        # Normalize to forward slashes; strip leading "./".
        norm = pat.lstrip("./")
        # Python 3.11/3.12 quirk: `Path.glob("foo/**")` matches directories
        # only, not their files. 3.13+ matches both. Normalize to `foo/**/*`
        # so behavior is consistent across versions.
        if norm == "**" or norm.endswith("/**"):
            norm = norm + "/*"
        for p in base.glob(norm):
            if p.is_file():
                seen[p.resolve()] = None
    return sorted(seen.keys())


def snapshot(
    base: Path,
    patterns: list[str],
) -> dict[str, FileSnapshot]:
    """Map relative path → FileSnapshot for every file currently matched.

    Args:
        base: directory the patterns are relative to (typically the
            scenario `cwd` inside the sandbox).
        patterns: glob patterns from skill `eval.yaml` `artifacts` (or
            scenario `artifacts_override`).

    Returns:
        dict keyed by rel path (forward slash, relative to `base`).
    """
    base = base.resolve()
    out: dict[str, FileSnapshot] = {}
    for path in _glob_relative(base, patterns):
        rel = str(path.relative_to(base)).replace("\\", "/")
        out[rel] = FileSnapshot(
            rel_path=rel,
            sha256=_sha256_file(path),
            size=path.stat().st_size,
        )
    return out


@dataclass
class ArtifactDiff:
    """Result of (post − pre) snapshot diff."""

    added: list[FileSnapshot] = field(default_factory=list)
    changed: list[FileSnapshot] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def produced(self) -> list[FileSnapshot]:
        """Artifacts to ship into __reports/ — added + changed."""
        return [*self.added, *self.changed]


def diff(
    pre: dict[str, FileSnapshot],
    post: dict[str, FileSnapshot],
) -> ArtifactDiff:
    """Compute (added, changed, deleted) from pre and post snapshots."""
    out = ArtifactDiff()
    for rel, snap in post.items():
        prev = pre.get(rel)
        if prev is None:
            out.added.append(snap)
        elif prev.sha256 != snap.sha256:
            out.changed.append(snap)
    for rel in pre:
        if rel not in post:
            out.deleted.append(rel)
    return out


def copy_into_report(
    base: Path,
    snaps: list[FileSnapshot],
    report_artifacts_dir: Path,
) -> None:
    """Copy each produced artifact under `report_artifacts_dir/<rel>`.

    Preserves the relative path so reports retain the cwd-relative tree.
    """
    report_artifacts_dir.mkdir(parents=True, exist_ok=True)
    for snap in snaps:
        src = (base / snap.rel_path).resolve()
        dst = report_artifacts_dir / snap.rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
