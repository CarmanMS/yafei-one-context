"""Shared fixtures for recorder tests.

Isolates `ONECXT_RECORDER_ROOT` per test so concurrent / sequential
runs do not see each other's active.json.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def recorder_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    root = tmp_path / "onecxt-recorder"
    monkeypatch.setenv("ONECXT_RECORDER_ROOT", str(root))
    return root


@pytest.fixture()
def repo_with_skill(tmp_path: Path) -> Path:
    """A minimal repo tree with `skills/demo/SKILL.md` present."""
    root = tmp_path / "repo"
    (root / "skills" / "demo").mkdir(parents=True)
    (root / "skills" / "demo" / "SKILL.md").write_text("# demo", encoding="utf-8")
    return root
