"""tmp-directory sandbox for eval runs (Phase 2.0+ · ISS-021).

Three driver paths (selected automatically via `_detect_driver()`):

- ``apfs_clonefile`` (macOS APFS): ``cp -cR <repo_root> <sandbox>/``
- ``linux_reflink`` (Btrfs/XFS):   ``cp -r --reflink=auto <repo_root> <sandbox>/``
- ``git_archive`` (fallback):      ``git archive HEAD | tar -x -C <sandbox>/``

clonefile / reflink semantics
  - COW, ≈0 disk cost, millisecond-scale
  - Includes uncommitted working-tree changes (the killer feature vs Phase 1
    git_archive)
  - Includes a full ``.git/``
  - ``sandbox_includes`` is **ignored** here (whole-repo COW is already free
    and a partial COW would break real-environment fidelity)

git_archive semantics (fallback only)
  - Tracked files at HEAD only (**no uncommitted changes** — warns)
  - ``.git/`` excluded unless ``include_git=True``
  - ``sandbox_includes`` is honoured as a ``git archive`` pathspec, auto-augmented
    with a set of always-include roots (``CLAUDE.md`` / ``.claude/`` /
    ``knowledge/standards/`` / ``evals/`` / ``meta/``); paths not present under
    HEAD are silently dropped to avoid ``git archive`` aborting.
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DRIVER_APFS = "apfs_clonefile"
DRIVER_REFLINK = "linux_reflink"
DRIVER_ARCHIVE = "git_archive"

_VALID_DRIVERS = frozenset({DRIVER_APFS, DRIVER_REFLINK, DRIVER_ARCHIVE})

# Auto-included roots when sandbox_includes is set (git_archive driver only).
# Caller (runner) is responsible for appending skill-/target_path-specific
# roots (`skills/<skill>/`, `features/_evals/<target_path>/`) since prepare()
# is intentionally skill-agnostic.
_AUTO_INCLUDES: tuple[str, ...] = (
    "CLAUDE.md",
    ".claude/",
    "knowledge/standards/",
    "evals/",
    "meta/",
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def new_run_id() -> str:
    """Generate a run id of the form ``<unix_ts>-<rand6>``."""
    return f"{int(time.time())}-{secrets.token_hex(3)}"


@dataclass
class Sandbox:
    """A prepared sandbox directory.

    Required new fields (Stage 2.0.1 contract):
      - ``path``: sandbox root on disk (``/tmp/onecxt-eval-<run_id>/``)
      - ``driver``: one of ``apfs_clonefile`` / ``linux_reflink`` / ``git_archive``
      - ``working_tree_sha``: sha256 of ``git status --porcelain`` at sandbox
        creation time; identifies the working-tree snapshot being evaluated

    Convenience / legacy fields (kept so existing call sites such as
    ``runner.py``'s ``sandbox.run_id`` / ``sandbox.git_commit`` keep working
    until Stage 2.0.2 migrates them).
    """

    path: Path
    driver: str
    working_tree_sha: str
    # Convenience fields:
    run_id: str = ""
    repo_root: Path = field(default_factory=Path)
    git_commit: str = "unknown"
    include_git: bool = False


# ---------------------------------------------------------------------------
# Driver detection
# ---------------------------------------------------------------------------

def _detect_driver() -> str:
    """Pick the best sandbox driver for the current host.

    macOS + APFS → ``apfs_clonefile``
    Linux + tmpfs type ∈ {btrfs, xfs} → ``linux_reflink``
    Everything else → ``git_archive`` (safe fallback)
    """
    sys_name = platform.system()

    if sys_name == "Darwin":
        try:
            r = subprocess.run(
                ["diskutil", "info", "/"],
                capture_output=True, text=True, check=False,
            )
        except FileNotFoundError:
            return DRIVER_ARCHIVE
        if r.returncode != 0:
            return DRIVER_ARCHIVE
        for line in r.stdout.splitlines():
            if "File System Personality" in line and "APFS" in line:
                return DRIVER_APFS
        return DRIVER_ARCHIVE

    if sys_name == "Linux":
        try:
            r = subprocess.run(
                ["stat", "-f", "-c", "%T", "/tmp"],
                capture_output=True, text=True, check=False,
            )
        except FileNotFoundError:
            return DRIVER_ARCHIVE
        if r.returncode == 0 and r.stdout.strip() in {"btrfs", "xfs"}:
            return DRIVER_REFLINK
        return DRIVER_ARCHIVE

    return DRIVER_ARCHIVE


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _tmp_root() -> Path:
    """Honour ``ONECXT_EVAL_TMP_ROOT`` so tests can redirect to a tmpdir."""
    env = os.environ.get("ONECXT_EVAL_TMP_ROOT")
    if env:
        return Path(env)
    return Path(tempfile.gettempdir())


def _git_commit(repo_root: Path) -> str:
    """Best-effort ``HEAD`` resolve. Returns ``unknown`` on failure."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return out or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _working_tree_sha(repo_root: Path) -> str:
    """sha256 of ``git status --porcelain`` output (uncommitted-change fingerprint)."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = b""
    return hashlib.sha256(out).hexdigest()


def _path_in_head(repo_root: Path, pathspec: str) -> bool:
    """Return True iff ``pathspec`` (file or dir) has any tracked content
    under HEAD. Used to silently drop nonexistent auto-includes so
    ``git archive`` doesn't abort with "pathspec did not match".
    """
    check = pathspec.rstrip("/")
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "ls-tree", "-r",
             "--name-only", "HEAD", "--", check],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


# ---------------------------------------------------------------------------
# Driver implementations
# ---------------------------------------------------------------------------

def _populate_clonefile(repo_root: Path, sandbox_path: Path) -> None:
    """macOS APFS COW copy. Do NOT pre-mkdir sandbox_path — ``cp -cR`` will
    create it as a clone of ``repo_root``."""
    r = subprocess.run(
        ["cp", "-cR", str(repo_root), str(sandbox_path)],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"cp -cR failed (rc={r.returncode}): {r.stderr.strip()}"
        )


def _populate_reflink(repo_root: Path, sandbox_path: Path) -> None:
    """Linux Btrfs/XFS reflink COW copy. Same pre-mkdir contract as clonefile."""
    r = subprocess.run(
        ["cp", "-r", "--reflink=auto", str(repo_root), str(sandbox_path)],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"cp -r --reflink=auto failed (rc={r.returncode}): {r.stderr.strip()}"
        )


def _populate_archive(
    repo_root: Path,
    sandbox_path: Path,
    *,
    include_git: bool,
    pathspec: list[str] | None,
) -> None:
    """``git archive HEAD [-- <pathspec>...] | tar -x`` into a pre-mkdir-ed
    sandbox_path. ``.git/`` is copied separately when ``include_git``."""
    cmd = ["git", "archive", "HEAD"]
    if pathspec:
        cmd.append("--")
        cmd.extend(pathspec)

    archive = subprocess.Popen(
        cmd, cwd=str(repo_root), stdout=subprocess.PIPE,
    )
    try:
        extract = subprocess.Popen(
            ["tar", "-x", "-C", str(sandbox_path)],
            stdin=archive.stdout,
        )
        if archive.stdout is not None:
            archive.stdout.close()  # let archive receive SIGPIPE on extract death
        extract_rc = extract.wait()
        archive_rc = archive.wait()
    except Exception:
        archive.kill()
        archive.wait()
        raise

    if archive_rc != 0 or extract_rc != 0:
        raise RuntimeError(
            f"git archive | tar -x failed "
            f"(archive rc={archive_rc}, tar rc={extract_rc})"
        )

    if include_git:
        shutil.copytree(repo_root / ".git", sandbox_path / ".git")


# ---------------------------------------------------------------------------
# Public API — prepare / teardown / clean
# ---------------------------------------------------------------------------

def prepare(
    run_id: str,
    *,
    repo_root: Path | None = None,
    force_driver: str | None = None,
    include_git: bool = False,
    sandbox_includes: list[str] | None = None,
) -> Sandbox:
    """Create ``/tmp/onecxt-eval-<run_id>/`` and populate via the selected driver.

    Parameters
    ----------
    run_id
        Caller-supplied run id (use :func:`new_run_id` to generate).
    repo_root
        Source repo root. Defaults to the current working directory.
    force_driver
        Bypass platform detection; must be one of ``apfs_clonefile`` /
        ``linux_reflink`` / ``git_archive``. Used for tests and for scenarios
        that pin a driver via ``scenario.yaml``.
    include_git
        Only meaningful when driver is ``git_archive``: also ``cp -r`` the
        ``.git/`` directory into the sandbox. clonefile / reflink always have
        ``.git/`` by virtue of whole-repo COW.
    sandbox_includes
        Only meaningful when driver is ``git_archive``: a list of pathspecs to
        pass to ``git archive HEAD -- <includes>``. The function auto-appends
        a small set of always-needed roots (``CLAUDE.md`` / ``.claude/`` /
        ``knowledge/standards/`` / ``evals/`` / ``meta/``); paths absent from
        HEAD are silently dropped.
    """
    if not run_id or not isinstance(run_id, str):
        raise ValueError("run_id must be a non-empty string")
    if force_driver is not None and force_driver not in _VALID_DRIVERS:
        raise ValueError(
            f"force_driver must be one of {sorted(_VALID_DRIVERS)}, "
            f"got {force_driver!r}"
        )

    rr = (repo_root or Path.cwd()).resolve()
    if not (rr / ".git").exists():
        raise RuntimeError(f"Not a git repository (no .git at): {rr}")

    sandbox_path = _tmp_root() / f"onecxt-eval-{run_id}"
    if sandbox_path.exists():
        raise RuntimeError(f"sandbox already exists: {sandbox_path}")

    # Ensure the tmp root itself exists; the per-run dir is created by the
    # driver (clonefile/reflink) or here (git_archive).
    sandbox_path.parent.mkdir(parents=True, exist_ok=True)

    driver = force_driver or _detect_driver()

    # Snapshot working-tree fingerprint BEFORE materialising — meaningful
    # only on COW paths but cheap and uniform.
    wt_sha = _working_tree_sha(rr)

    try:
        if driver == DRIVER_APFS:
            if sandbox_includes:
                logger.warning(
                    "sandbox_includes 在 %s 路径下被忽略（COW 全量已包含）",
                    DRIVER_APFS,
                )
            _populate_clonefile(rr, sandbox_path)

        elif driver == DRIVER_REFLINK:
            if sandbox_includes:
                logger.warning(
                    "sandbox_includes 在 %s 路径下被忽略（COW 全量已包含）",
                    DRIVER_REFLINK,
                )
            _populate_reflink(rr, sandbox_path)

        elif driver == DRIVER_ARCHIVE:
            sandbox_path.mkdir(parents=True, exist_ok=False)
            logger.warning(
                "git_archive 兜底路径下，未 commit 改动不会被评测，建议先 commit"
            )
            pathspec = _build_archive_pathspec(rr, sandbox_includes)
            _populate_archive(
                rr, sandbox_path,
                include_git=include_git, pathspec=pathspec,
            )
        else:  # pragma: no cover — guarded above
            raise RuntimeError(f"unknown driver: {driver}")
    except Exception:
        shutil.rmtree(sandbox_path, ignore_errors=True)
        raise

    return Sandbox(
        path=sandbox_path,
        driver=driver,
        working_tree_sha=wt_sha,
        run_id=run_id,
        repo_root=rr,
        git_commit=_git_commit(rr),
        include_git=include_git,
    )


def _build_archive_pathspec(
    repo_root: Path,
    sandbox_includes: list[str] | None,
) -> list[str] | None:
    """Compose the git-archive pathspec for the git_archive driver.

    Returns None when no includes were declared (full repo archive).
    Otherwise returns ``user_includes + filtered_auto_includes`` and prints
    the activation banner to stderr.
    """
    user_includes = [p for p in (sandbox_includes or []) if p]
    if not user_includes:
        return None

    auto_includes = [
        p for p in _AUTO_INCLUDES if _path_in_head(repo_root, p)
    ]
    pathspec = user_includes + auto_includes

    # Activation banner per tech_design §2.7 / brief 2.0.1.f. Use print to
    # stderr (not logger) so it always surfaces in the operator's terminal
    # regardless of root log level.
    print(
        f"sandbox_includes 生效：{len(user_includes)} 条用户声明 + "
        f"{len(auto_includes)} 条必含根；git archive pathspec 模式",
        file=sys.stderr,
    )
    return pathspec


def teardown(sandbox: Sandbox, *, keep: bool = False) -> None:
    """Remove the sandbox directory unless ``keep`` is True."""
    if keep:
        return
    if not sandbox.path.exists():
        return
    shutil.rmtree(sandbox.path, ignore_errors=True)


def clean_residual() -> int:
    """Remove every ``/tmp/onecxt-eval-*`` left behind by killed runs.

    Returns the count of directories actually removed.
    """
    root = _tmp_root()
    if not root.is_dir():
        return 0
    n = 0
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.startswith("onecxt-eval-"):
            shutil.rmtree(entry, ignore_errors=True)
            n += 1
    return n


def clean_orphans() -> list[Path]:
    """Backward-compat alias of :func:`clean_residual` that returns the list
    of paths actually removed (CLI compat — ``onecxt eval clean`` still
    iterates the return value to print one path per line).
    """
    root = _tmp_root()
    removed: list[Path] = []
    if not root.is_dir():
        return removed
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.startswith("onecxt-eval-"):
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry)
    return removed
