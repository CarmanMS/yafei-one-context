"""Overlay tests for the Stage 2.0.3 single-file patch model (ISS-022)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from one_context.eval import fixture as fix
from one_context.eval.scenario_config import OverlayConfig, OverlayItem


def _make_overlay(items: list[tuple[str, str]]) -> OverlayConfig:
    return OverlayConfig(apply=[OverlayItem(src=s, dst=d) for s, d in items])


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_apply_overlay_none_returns_empty(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    res = fix.apply_overlay(sandbox, "features/_evals/foo/", None, scn)
    assert res == []


def test_apply_overlay_empty_apply_returns_empty(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    res = fix.apply_overlay(sandbox, "features/_evals/foo/", OverlayConfig(apply=[]), scn)
    assert res == []


def test_apply_overlay_single_file_interpolates_target_path(tmp_path: Path) -> None:
    """{{ target_path }} in dst is replaced verbatim, file lands, sha256 recorded."""
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    _write(scn / "patches" / "spec-override.md", "PATCHED-SPEC-CONTENT")

    target_path = "features/_evals/content-pipeline/agent-long-term-memory-content-ready/"
    overlay = _make_overlay([
        ("patches/spec-override.md", "{{ target_path }}spec.md"),
    ])
    res = fix.apply_overlay(sandbox, target_path, overlay, scn)

    assert len(res) == 1
    item = res[0]
    assert item.src == Path("patches/spec-override.md")
    expected_dst = sandbox / target_path / "spec.md"
    assert item.dst == expected_dst.resolve()
    assert expected_dst.read_text(encoding="utf-8") == "PATCHED-SPEC-CONTENT"
    assert item.sha256 == _sha256(b"PATCHED-SPEC-CONTENT")


def test_apply_overlay_interpolation_tolerates_whitespace_variants(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    _write(scn / "a.md", "A")
    _write(scn / "b.md", "B")

    target_path = "x/"
    overlay = _make_overlay([
        ("a.md", "{{target_path}}out-a.md"),       # no spaces
        ("b.md", "{{   target_path   }}out-b.md"), # extra spaces
    ])
    res = fix.apply_overlay(sandbox, target_path, overlay, scn)

    assert (sandbox / "x" / "out-a.md").read_text(encoding="utf-8") == "A"
    assert (sandbox / "x" / "out-b.md").read_text(encoding="utf-8") == "B"
    assert len(res) == 2


def test_apply_overlay_missing_src_raises(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    overlay = _make_overlay([("ghost.md", "{{ target_path }}spec.md")])
    with pytest.raises(FileNotFoundError, match="overlay src missing"):
        fix.apply_overlay(sandbox, "x/", overlay, scn)


def test_apply_overlay_auto_mkdir_parent(tmp_path: Path) -> None:
    """dst parent dirs that don't exist are created automatically."""
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    _write(scn / "deep.md", "DEEP")
    overlay = _make_overlay([
        ("deep.md", "very/deep/nested/path/output.md"),
    ])
    res = fix.apply_overlay(sandbox, "", overlay, scn)
    assert len(res) == 1
    assert (sandbox / "very" / "deep" / "nested" / "path" / "output.md").read_text(encoding="utf-8") == "DEEP"


def test_apply_overlay_multiple_items_processed_in_order(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    _write(scn / "first.md", "FIRST")
    _write(scn / "second.md", "SECOND")
    _write(scn / "third.md", "THIRD")
    overlay = _make_overlay([
        ("first.md", "a.md"),
        ("second.md", "b.md"),
        ("third.md", "c.md"),
    ])
    res = fix.apply_overlay(sandbox, "", overlay, scn)
    assert [r.src.name for r in res] == ["first.md", "second.md", "third.md"]
    assert (sandbox / "a.md").read_text(encoding="utf-8") == "FIRST"
    assert (sandbox / "b.md").read_text(encoding="utf-8") == "SECOND"
    assert (sandbox / "c.md").read_text(encoding="utf-8") == "THIRD"


def test_apply_overlay_replace_semantics_overwrites_existing(tmp_path: Path) -> None:
    """No `mode` field — overlay always replaces an existing file at dst."""
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    (sandbox / "spec.md").write_text("ORIGINAL", encoding="utf-8")

    scn = tmp_path / "scn"
    scn.mkdir()
    _write(scn / "patch.md", "REPLACED")

    overlay = _make_overlay([("patch.md", "spec.md")])
    res = fix.apply_overlay(sandbox, "", overlay, scn)

    assert len(res) == 1
    assert (sandbox / "spec.md").read_text(encoding="utf-8") == "REPLACED"
    assert res[0].sha256 == _sha256(b"REPLACED")


def test_apply_overlay_dst_escape_rejected(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    scn = tmp_path / "scn"
    scn.mkdir()
    _write(scn / "a.md", "A")
    overlay = _make_overlay([("a.md", "../outside.md")])
    with pytest.raises(ValueError, match="escapes sandbox"):
        fix.apply_overlay(sandbox, "", overlay, scn)
