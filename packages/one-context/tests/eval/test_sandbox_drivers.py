"""Sandbox driver tests (Phase 2.0 / Stage 2.0.1 · ISS-021).

Covers:
  * `_detect_driver()` for the 3 supported platform classes
  * `prepare()` per-driver dispatch (clonefile / reflink / git_archive)
  * `working_tree_sha` is populated correctly
  * `force_driver=` override
  * `teardown()` removes the sandbox dir
  * `sandbox_includes` semantics (ignored on clonefile, honoured on
    git_archive with auto-augmented roots + activation banner)
  * scenario_config schema accepts the new `sandbox_driver` field
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from one_context.eval import sandbox as sb
from one_context.eval.scenario_config import ScenarioConfig


# ---------------------------------------------------------------------------
# Platform guard for the real-COW test case
# ---------------------------------------------------------------------------

_HOST_DRIVER = sb._detect_driver()
IS_MAC_APFS = sys.platform == "darwin" and _HOST_DRIVER == sb.DRIVER_APFS


# ---------------------------------------------------------------------------
# _detect_driver — 3 platform branches (subprocess mocked)
# ---------------------------------------------------------------------------

def _fake_run_factory(by_cmd_key: dict[str, SimpleNamespace]) -> Callable:
    """Return a subprocess.run replacement that dispatches on the leading
    command name. ``by_cmd_key`` maps the head-of-argv (e.g. ``diskutil``,
    ``stat``) to a SimpleNamespace mimicking CompletedProcess."""
    def fake_run(argv, **_kw):
        head = argv[0] if argv else ""
        if head in by_cmd_key:
            return by_cmd_key[head]
        return SimpleNamespace(returncode=1, stdout="", stderr="")
    return fake_run


def test_detect_driver_macos_apfs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sb.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        sb.subprocess, "run",
        _fake_run_factory({
            "diskutil": SimpleNamespace(
                returncode=0,
                stdout=(
                    "Device Identifier: disk3s1s1\n"
                    "   File System Personality:   APFS\n"
                    "   Volume Name:               Macintosh HD\n"
                ),
                stderr="",
            ),
        }),
    )
    assert sb._detect_driver() == sb.DRIVER_APFS


def test_detect_driver_macos_non_apfs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sb.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        sb.subprocess, "run",
        _fake_run_factory({
            "diskutil": SimpleNamespace(
                returncode=0,
                stdout="   File System Personality:   HFS+\n",
                stderr="",
            ),
        }),
    )
    assert sb._detect_driver() == sb.DRIVER_ARCHIVE


def test_detect_driver_linux_btrfs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sb.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        sb.subprocess, "run",
        _fake_run_factory({
            "stat": SimpleNamespace(returncode=0, stdout="btrfs\n", stderr=""),
        }),
    )
    assert sb._detect_driver() == sb.DRIVER_REFLINK


def test_detect_driver_linux_xfs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sb.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        sb.subprocess, "run",
        _fake_run_factory({
            "stat": SimpleNamespace(returncode=0, stdout="xfs\n", stderr=""),
        }),
    )
    assert sb._detect_driver() == sb.DRIVER_REFLINK


def test_detect_driver_linux_ext4_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sb.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        sb.subprocess, "run",
        _fake_run_factory({
            "stat": SimpleNamespace(returncode=0, stdout="ext2/ext3\n", stderr=""),
        }),
    )
    assert sb._detect_driver() == sb.DRIVER_ARCHIVE


def test_detect_driver_windows_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sb.platform, "system", lambda: "Windows")
    # subprocess.run should not be hit on this branch; if it is, return failure
    monkeypatch.setattr(
        sb.subprocess, "run",
        _fake_run_factory({}),
    )
    assert sb._detect_driver() == sb.DRIVER_ARCHIVE


# ---------------------------------------------------------------------------
# prepare() — dataclass fields, run_id, working_tree_sha, force_driver
# ---------------------------------------------------------------------------

def test_prepare_populates_sandbox_dataclass(git_repo_root: Path) -> None:
    """The new contract requires path / driver / working_tree_sha."""
    rid = sb.new_run_id()
    box = sb.prepare(rid, repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE)
    try:
        assert box.path.is_dir()
        assert box.path.name == f"onecxt-eval-{rid}"
        assert box.driver == sb.DRIVER_ARCHIVE
        # working_tree_sha is a hex sha256 string (64 chars)
        assert len(box.working_tree_sha) == 64
        int(box.working_tree_sha, 16)  # raises if not hex
        # legacy convenience fields stay populated for runner.py compat
        assert box.run_id == rid
        assert box.repo_root == git_repo_root.resolve()
    finally:
        sb.teardown(box)


def test_prepare_working_tree_sha_reflects_uncommitted(
    git_repo_root: Path,
) -> None:
    """Adding an unstaged file changes the sha; verifying that
    `git status --porcelain` is genuinely the input to the sha256."""
    rid_clean = sb.new_run_id()
    box_clean = sb.prepare(
        rid_clean, repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
    )
    try:
        # baseline sha against a clean tree (== sha of empty output)
        empty_sha = box_clean.working_tree_sha
    finally:
        sb.teardown(box_clean)

    # Introduce an untracked file → status --porcelain output now non-empty
    (git_repo_root / "untracked.txt").write_text("dirty", encoding="utf-8")
    rid_dirty = sb.new_run_id()
    box_dirty = sb.prepare(
        rid_dirty, repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
    )
    try:
        assert box_dirty.working_tree_sha != empty_sha
    finally:
        sb.teardown(box_dirty)


def test_prepare_force_driver_overrides_detection(
    git_repo_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if the host detects clonefile, `force_driver=git_archive`
    must win."""
    monkeypatch.setattr(sb, "_detect_driver", lambda: sb.DRIVER_APFS)
    rid = sb.new_run_id()
    box = sb.prepare(
        rid, repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
    )
    try:
        assert box.driver == sb.DRIVER_ARCHIVE
        # git_archive does NOT bring `.git/` unless include_git=True
        assert not (box.path / ".git").exists()
    finally:
        sb.teardown(box)


def test_prepare_rejects_invalid_force_driver(git_repo_root: Path) -> None:
    with pytest.raises(ValueError, match="force_driver must be one of"):
        sb.prepare(
            sb.new_run_id(), repo_root=git_repo_root, force_driver="docker",
        )


def test_prepare_rejects_empty_run_id(git_repo_root: Path) -> None:
    with pytest.raises(ValueError, match="run_id must be a non-empty"):
        sb.prepare("", repo_root=git_repo_root)


def test_prepare_rejects_not_a_repo(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Not a git repository"):
        sb.prepare(
            sb.new_run_id(), repo_root=tmp_path, force_driver=sb.DRIVER_ARCHIVE,
        )


def test_prepare_existing_sandbox_path_raises(git_repo_root: Path) -> None:
    rid = "fixed-collision"
    box = sb.prepare(
        rid, repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
    )
    try:
        with pytest.raises(RuntimeError, match="already exists"):
            sb.prepare(
                rid, repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
            )
    finally:
        sb.teardown(box)


# ---------------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------------

def test_teardown_removes_sandbox(git_repo_root: Path) -> None:
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
    )
    p = box.path
    assert p.is_dir()
    sb.teardown(box)
    assert not p.exists()


def test_teardown_keep_preserves(git_repo_root: Path) -> None:
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
    )
    p = box.path
    sb.teardown(box, keep=True)
    assert p.is_dir()
    sb.teardown(box)  # actual cleanup
    assert not p.exists()


# ---------------------------------------------------------------------------
# git_archive driver — warn message
# ---------------------------------------------------------------------------

def test_git_archive_warns_about_uncommitted(
    git_repo_root: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="one_context.eval.sandbox"):
        box = sb.prepare(
            sb.new_run_id(), repo_root=git_repo_root,
            force_driver=sb.DRIVER_ARCHIVE,
        )
    try:
        msgs = [r.getMessage() for r in caplog.records]
        assert any("未 commit" in m for m in msgs), (
            f"expected '未 commit' warn, got: {msgs}"
        )
    finally:
        sb.teardown(box)


def test_git_archive_include_git_copies_dotgit(git_repo_root: Path) -> None:
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE, include_git=True,
    )
    try:
        assert (box.path / ".git").is_dir()
    finally:
        sb.teardown(box)


# ---------------------------------------------------------------------------
# APFS clonefile path — only meaningful on macOS APFS
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not IS_MAC_APFS,
    reason="clonefile real-COW case requires macOS APFS host",
)
def test_clonefile_captures_uncommitted_changes(git_repo_root: Path) -> None:
    """The killer feature: clonefile sees the working tree, including
    files that were never `git add`-ed."""
    # Write a file but DO NOT git add — git archive HEAD wouldn't see it
    (git_repo_root / "WIP-uncommitted.md").write_text(
        "in-progress", encoding="utf-8",
    )

    rid = sb.new_run_id()
    box = sb.prepare(rid, repo_root=git_repo_root)  # driver auto-detected = APFS
    try:
        assert box.driver == sb.DRIVER_APFS
        # the unstaged file MUST appear in the sandbox
        assert (box.path / "WIP-uncommitted.md").is_file()
        assert (box.path / "WIP-uncommitted.md").read_text() == "in-progress"
        # .git/ comes for free on the COW path
        assert (box.path / ".git").is_dir()
    finally:
        sb.teardown(box)


# ---------------------------------------------------------------------------
# sandbox_includes — clonefile ignores, git_archive honours + auto-augments
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not IS_MAC_APFS,
    reason="clonefile-ignore test needs the actual clonefile path",
)
def test_sandbox_includes_ignored_on_clonefile(
    git_repo_root: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="one_context.eval.sandbox"):
        box = sb.prepare(
            sb.new_run_id(), repo_root=git_repo_root,
            force_driver=sb.DRIVER_APFS,
            sandbox_includes=["skills/demo/"],
        )
    try:
        msgs = [r.getMessage() for r in caplog.records]
        assert any(
            "sandbox_includes" in m and "被忽略" in m for m in msgs
        ), f"expected clonefile-ignore warn, got: {msgs}"
    finally:
        sb.teardown(box)


def test_sandbox_includes_whitelist_applied_on_git_archive(
    git_repo_root: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The pathspec must actually limit what `git archive` extracts.
    We pass a user_include that exists (`features/x/`) and verify the
    sandbox contains it; other tracked paths NOT in user_includes nor
    auto_includes should NOT be present."""
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
        sandbox_includes=["features/"],
    )
    try:
        # whitelisted subtree present
        assert (box.path / "features" / "x" / "y" / "spec.md").is_file()
        # NOT in user_includes nor auto_includes (no CLAUDE.md / knowledge/ /
        # meta/ / evals/ in the conftest fixture; only .claude/ is)
        assert not (box.path / "README.md").exists()
        # auto-included root that exists in fixture: .claude/
        assert (box.path / ".claude" / "agents" / "dev.md").is_file()
    finally:
        sb.teardown(box)


def test_sandbox_includes_auto_root_filtering(git_repo_root: Path) -> None:
    """Auto-includes that DO NOT exist in HEAD must be silently dropped
    (otherwise `git archive` would abort with 'pathspec did not match')."""
    # Only .claude/ exists among the 5 auto roots; the rest must be filtered.
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
        sandbox_includes=["skills/demo/"],
    )
    try:
        assert (box.path / "skills" / "demo" / "SKILL.md").is_file()
        assert (box.path / ".claude" / "agents" / "dev.md").is_file()
        # things NOT in user nor (existing) auto includes
        assert not (box.path / "features" / "x" / "y" / "spec.md").exists()
        assert not (box.path / "README.md").exists()
    finally:
        sb.teardown(box)


def test_sandbox_includes_banner_prints_counts(
    git_repo_root: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Activation banner on stderr names BOTH counts (N user + M auto)."""
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
        sandbox_includes=["skills/demo/", "features/x/"],
    )
    try:
        err = capsys.readouterr().err
        assert "sandbox_includes 生效" in err
        # 2 user-declared
        assert "2 条用户声明" in err
        # 1 auto root that actually exists in HEAD (`.claude/`)
        assert "1 条必含根" in err
        assert "git archive pathspec 模式" in err
    finally:
        sb.teardown(box)


def test_sandbox_includes_none_does_not_filter(
    git_repo_root: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """With no sandbox_includes set, the full HEAD tree archives in
    (no pathspec, no banner)."""
    box = sb.prepare(
        sb.new_run_id(), repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
    )
    try:
        # tracked README is present (would be excluded by a pathspec)
        assert (box.path / "README.md").is_file()
        err = capsys.readouterr().err
        assert "sandbox_includes 生效" not in err
    finally:
        sb.teardown(box)


# ---------------------------------------------------------------------------
# scenario_config — sandbox_driver / sandbox_includes fields accepted
# ---------------------------------------------------------------------------

def test_scenario_config_accepts_sandbox_driver() -> None:
    cfg = ScenarioConfig.model_validate({
        "query": "noop",
        "target_path": "features/_evals/foo/",
        "sandbox_driver": "git_archive",
        "sandbox_includes": ["docs/architecture.md"],
    })
    assert cfg.sandbox_driver == "git_archive"
    assert cfg.sandbox_includes == ["docs/architecture.md"]


def test_scenario_config_sandbox_driver_optional() -> None:
    cfg = ScenarioConfig.model_validate({
        "query": "noop",
        "target_path": "features/_evals/foo/",
    })
    assert cfg.sandbox_driver is None
    assert cfg.sandbox_includes is None


def test_scenario_config_rejects_unknown_driver() -> None:
    with pytest.raises(Exception):  # noqa: B017  — pydantic ValidationError
        ScenarioConfig.model_validate({
            "query": "noop",
            "target_path": "features/_evals/foo/",
            "sandbox_driver": "docker",
        })


# ---------------------------------------------------------------------------
# clean_residual / clean_orphans
# ---------------------------------------------------------------------------

def test_clean_residual_returns_count(git_repo_root: Path) -> None:
    sb.prepare(
        "leak-a", repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
    )
    sb.prepare(
        "leak-b", repo_root=git_repo_root, force_driver=sb.DRIVER_ARCHIVE,
    )
    # leave both behind on purpose
    n = sb.clean_residual()
    assert n == 2
    # idempotent
    assert sb.clean_residual() == 0


def test_new_run_id_is_unique() -> None:
    a = sb.new_run_id()
    b = sb.new_run_id()
    assert a != b
    assert "-" in a


def test_clean_orphans_backward_compat(git_repo_root: Path) -> None:
    """Old CLI still calls `clean_orphans()` and iterates the returned
    list[Path]; verify that signature still works."""
    box = sb.prepare(
        "legacy-leak", repo_root=git_repo_root,
        force_driver=sb.DRIVER_ARCHIVE,
    )
    removed = sb.clean_orphans()
    assert isinstance(removed, list)
    assert box.path in [p for p in removed]
    assert not box.path.exists()
