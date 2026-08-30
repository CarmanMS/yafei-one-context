from __future__ import annotations

import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from one_context.repos import load_repos

logger = logging.getLogger("one_context.sync")


@dataclass
class SyncResult:
    label: str
    success: bool
    message: str


def sync_one(entry: dict[str, Any], root: Path) -> SyncResult:
    """Synchronise a single repository — clone, pull, or skip."""
    target = (root / entry["path"]).resolve()
    url = entry["url"]
    label = entry["id"]

    try:
        git_marker = target / ".git"
        if target.exists() and (git_marker.is_dir() or git_marker.is_file()):
            status = subprocess.run(
                ["git", "-C", str(target), "status", "--porcelain"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if status.returncode != 0:
                msg = f"[update-failed] {label}: git status exited {status.returncode}"
                logger.error(msg)
                return SyncResult(label=label, success=False, message=msg)
            if status.stdout.strip():
                msg = f"[dirty] {label}: commit or stash local changes before sync"
                logger.warning(msg)
                return SyncResult(label=label, success=False, message=msg)

            logger.info("[update] %s -> %s", label, target)
            result = subprocess.run(
                ["git", "-C", str(target), "pull", "--ff-only"],
                cwd=root,
                check=False,
                timeout=120,
            )
            if result.returncode != 0:
                msg = f"[update-failed] {label}: git pull exited {result.returncode}"
                logger.error(msg)
                return SyncResult(label=label, success=False, message=msg)
            return SyncResult(label=label, success=True, message=f"[update] {label}")

        if target.exists():
            msg = f"[skip] {label}: path exists but is not a git repo: {target}"
            logger.warning(msg)
            return SyncResult(label=label, success=False, message=msg)

        target.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[clone] %s -> %s", label, target)
        result = subprocess.run(
            ["git", "clone", url, str(target)], check=False, timeout=120,
        )
        if result.returncode != 0:
            msg = f"[clone-failed] {label}: git clone exited {result.returncode}"
            logger.error(msg)
            return SyncResult(label=label, success=False, message=msg)
        return SyncResult(label=label, success=True, message=f"[clone] {label}")
    except FileNotFoundError:
        msg = f"[failed] {label}: git executable not found"
    except subprocess.TimeoutExpired:
        msg = f"[failed] {label}: git command timed out after 120 seconds"
    logger.error(msg)
    return SyncResult(label=label, success=False, message=msg)


def sync_repositories(
    root: Path,
    select: list[str] | None,
    *,
    workers: int = 4,
) -> list[SyncResult]:
    """Synchronise repositories, optionally filtered by id/alias.

    Returns a list of :class:`SyncResult` — one per repo processed.
    """
    if workers <= 0:
        raise ValueError("workers must be greater than zero")
    entries, by_key = load_repos(root)
    if select:
        chosen: list[dict[str, Any]] = []
        for key in select:
            e = by_key.get(key.casefold())
            if not e:
                logger.error("Unknown id or alias: %r", key)
                raise SystemExit(2)
            if e not in chosen:
                chosen.append(e)
        to_run = chosen
    else:
        to_run = entries

    results: list[SyncResult] = []
    if workers <= 1 or len(to_run) <= 1:
        for entry in to_run:
            results.append(sync_one(entry, root))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(sync_one, entry, root): entry for entry in to_run}
            for future in as_completed(futures):
                results.append(future.result())

    logger.info("Done. %d/%d succeeded.", sum(r.success for r in results), len(results))
    return results
