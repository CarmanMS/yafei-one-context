"""Artifact snapshot tests — sha256 catches mtime-preserved + same-second writes."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from one_context.eval import artifacts as A


def test_snapshot_records_sha_size(tmp_path: Path) -> None:
    base = tmp_path / "base"
    (base / "production").mkdir(parents=True)
    f = base / "production" / "out.md"
    f.write_text("hello", encoding="utf-8")

    snap = A.snapshot(base, ["production/**"])
    assert "production/out.md" in snap
    s = snap["production/out.md"]
    assert s.size == 5
    assert len(s.sha256) == 64


def test_diff_added_changed_deleted(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "a.md").write_text("A", encoding="utf-8")
    (base / "b.md").write_text("B", encoding="utf-8")
    pre = A.snapshot(base, ["*.md"])

    # mutate: change a, add c, delete b
    (base / "a.md").write_text("A2", encoding="utf-8")
    (base / "c.md").write_text("C", encoding="utf-8")
    (base / "b.md").unlink()
    post = A.snapshot(base, ["*.md"])

    diff = A.diff(pre, post)
    assert [s.rel_path for s in diff.added] == ["c.md"]
    assert [s.rel_path for s in diff.changed] == ["a.md"]
    assert diff.deleted == ["b.md"]


def test_mtime_preserved_via_copy2_still_caught(tmp_path: Path) -> None:
    """ISS-015: skill writes via shutil.copy2 keep src mtime; sha256 still catches it."""
    base = tmp_path / "base"
    (base / "production").mkdir(parents=True)
    src = tmp_path / "src.md"
    src.write_text("A", encoding="utf-8")

    pre_existing = base / "production" / "out.md"
    pre_existing.write_text("OLD", encoding="utf-8")
    # bump pre_existing mtime to 1h ago so copy2 will set an EARLIER mtime
    far_past = time.time() - 3600
    os.utime(pre_existing, (far_past, far_past))

    pre = A.snapshot(base, ["production/**"])

    # simulate skill behavior: copy2 preserves src mtime (fresh, NOW)
    shutil.copy2(src, pre_existing)
    # but in some flows mtime can land *earlier* than pre — emulate that
    far_far_past = time.time() - 7200
    os.utime(pre_existing, (far_far_past, far_far_past))

    post = A.snapshot(base, ["production/**"])
    diff = A.diff(pre, post)
    assert [s.rel_path for s in diff.changed] == ["production/out.md"]


def test_same_second_writes_caught_by_sha(tmp_path: Path) -> None:
    """ISS-015: pre & post writes in the same fs-second still detected by sha."""
    base = tmp_path / "base"
    base.mkdir()
    p = base / "x.md"
    p.write_text("X", encoding="utf-8")
    pre = A.snapshot(base, ["*.md"])

    # write again within the same second; force same mtime to be safe
    pre_mtime = p.stat().st_mtime
    p.write_text("Y", encoding="utf-8")
    os.utime(p, (pre_mtime, pre_mtime))

    post = A.snapshot(base, ["*.md"])
    diff = A.diff(pre, post)
    assert [s.rel_path for s in diff.changed] == ["x.md"]


def test_copy_into_report_preserves_tree(tmp_path: Path) -> None:
    base = tmp_path / "base"
    (base / "a" / "b").mkdir(parents=True)
    (base / "a" / "b" / "c.md").write_text("X", encoding="utf-8")
    snap = A.snapshot(base, ["a/**"])
    out = tmp_path / "out"
    A.copy_into_report(base, list(snap.values()), out)
    assert (out / "a" / "b" / "c.md").read_text(encoding="utf-8") == "X"
