"""Overlay schema tests for scenario_config (ISS-022, Stage 2.0.3).

Complements `test_config.py`. Lives in its own file so the overlay-specific
surface stays compact and locatable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from one_context.eval.scenario_config import (
    OverlayConfig,
    OverlayItem,
    load_scenario,
)


def _write_scenario(scn: Path, body: str) -> None:
    scn.mkdir()
    (scn / "scenario.yaml").write_text(body, encoding="utf-8")


def test_overlay_field_defaults_to_none(tmp_path: Path) -> None:
    """A scenario.yaml without an `overlay:` block parses with overlay=None.

    NOTE: this calls load_scenario rather than constructing ScenarioConfig
    directly to avoid the pydantic-v2 `deprecated=True` descriptor write
    issue in Stage 2.0.2's compat layer.
    """
    _write_scenario(
        tmp_path / "s",
        "query: q\ntarget_path: features/_evals/foo/\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.overlay is None


def test_overlay_with_apply_parses(tmp_path: Path) -> None:
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: features/_evals/foo/\n"
        "overlay:\n"
        "  apply:\n"
        "    - src: patches/p1.md\n"
        "      dst: '{{ target_path }}p1.md'\n"
        "    - src: patches/p2.md\n"
        "      dst: '{{ target_path }}sub/p2.md'\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.overlay is not None
    assert len(cfg.overlay.apply) == 2
    assert cfg.overlay.apply[0].src == "patches/p1.md"
    assert cfg.overlay.apply[0].dst == "{{ target_path }}p1.md"
    assert cfg.overlay.apply[1].dst == "{{ target_path }}sub/p2.md"


def test_overlay_empty_apply_parses(tmp_path: Path) -> None:
    """`overlay: { apply: [] }` is valid (no-op overlay)."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: x/\n"
        "overlay:\n"
        "  apply: []\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.overlay is not None
    assert cfg.overlay.apply == []


def test_overlay_apply_extra_field_rejected(tmp_path: Path) -> None:
    """OverlayItem has extra='forbid'; typo in field name should error."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: x/\n"
        "overlay:\n"
        "  apply:\n"
        "    - src: a.md\n"
        "      dst: b.md\n"
        "      mode: replace\n",  # legacy/typo field
    )
    with pytest.raises(Exception):
        load_scenario(tmp_path / "s")


def test_overlay_apply_missing_src_rejected(tmp_path: Path) -> None:
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: x/\n"
        "overlay:\n"
        "  apply:\n"
        "    - dst: b.md\n",
    )
    with pytest.raises(Exception):
        load_scenario(tmp_path / "s")


def test_overlay_apply_missing_dst_rejected(tmp_path: Path) -> None:
    """No default for `dst` — must be explicit (no implicit '.')."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: x/\n"
        "overlay:\n"
        "  apply:\n"
        "    - src: a.md\n",
    )
    with pytest.raises(Exception):
        load_scenario(tmp_path / "s")


def test_legacy_fixture_block_rejected_with_migration_hint(tmp_path: Path) -> None:
    """ISS-022: old `fixture:` block must raise with a clear migration hint."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: x/\n"
        "fixture:\n"
        "  mode: overlay-and-replace\n"
        "  apply:\n"
        "    - src: ./fixture/\n"
        "      dst: .\n",
    )
    with pytest.raises(ValueError, match="fixture.*no longer supported"):
        load_scenario(tmp_path / "s")


def test_overlay_construction_via_python_api() -> None:
    """OverlayConfig / OverlayItem are usable from Python (for runner tests)."""
    overlay = OverlayConfig(apply=[
        OverlayItem(src="a.md", dst="{{ target_path }}out.md"),
    ])
    assert overlay.apply[0].src == "a.md"
    assert overlay.apply[0].dst == "{{ target_path }}out.md"


# ── Stage 2.X.4: provider.model is now optional ───────────────────────────


def test_provider_model_optional_defaults_to_none(tmp_path: Path) -> None:
    """Omit provider.model entirely → model=None; runner resolves at runtime."""
    _write_scenario(
        tmp_path / "s",
        "query: q\ntarget_path: features/_evals/foo/\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.provider.model is None


def test_provider_model_explicit_value_preserved(tmp_path: Path) -> None:
    _write_scenario(
        tmp_path / "s",
        "query: q\ntarget_path: features/_evals/foo/\nprovider:\n  model: GLM-5.1\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.provider.model == "GLM-5.1"


def test_provider_model_empty_string_rejected(tmp_path: Path) -> None:
    """Empty-string model is a YAML smell — reject with a clear hint."""
    _write_scenario(
        tmp_path / "s",
        "query: q\ntarget_path: features/_evals/foo/\nprovider:\n  model: ''\n",
    )
    with pytest.raises(Exception) as exc:
        load_scenario(tmp_path / "s")
    assert "empty" in str(exc.value).lower()


# ── session_inject schema (ISS-024 / Stage 2.7.A) ──────────────────────────


def test_session_inject_defaults_to_none(tmp_path: Path) -> None:
    """A scenario.yaml without a `session_inject:` block parses with None.

    Critical for backward compat: every existing scenario.yaml in the repo
    must keep working unchanged.
    """
    _write_scenario(
        tmp_path / "s",
        "query: q\ntarget_path: features/_evals/foo/\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.session_inject is None


def test_session_inject_disabled_parses(tmp_path: Path) -> None:
    """`enabled: false` parses (no mock_rounds_dir required)."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: features/_evals/foo/\n"
        "session_inject:\n"
        "  enabled: false\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.session_inject is not None
    assert cfg.session_inject.enabled is False
    assert cfg.session_inject.mock_rounds_dir is None


def test_session_inject_enabled_with_dir(tmp_path: Path) -> None:
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: features/_evals/foo/\n"
        "session_inject:\n"
        "  enabled: true\n"
        "  mock_rounds_dir: mock_rounds/\n"
        "  schema_version: '2.1.156'\n",
    )
    cfg = load_scenario(tmp_path / "s")
    assert cfg.session_inject is not None
    assert cfg.session_inject.enabled is True
    assert cfg.session_inject.mock_rounds_dir == "mock_rounds/"
    assert cfg.session_inject.schema_version == "2.1.156"


def test_session_inject_enabled_without_dir_rejected(tmp_path: Path) -> None:
    """enabled=true requires a non-empty mock_rounds_dir — fail fast."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: features/_evals/foo/\n"
        "session_inject:\n"
        "  enabled: true\n",
    )
    with pytest.raises(Exception) as exc:
        load_scenario(tmp_path / "s")
    msg = str(exc.value).lower()
    assert "mock_rounds_dir" in msg


def test_session_inject_extra_field_rejected(tmp_path: Path) -> None:
    """SessionInjectConfig has extra='forbid'; typos must surface early."""
    _write_scenario(
        tmp_path / "s",
        "query: q\n"
        "target_path: features/_evals/foo/\n"
        "session_inject:\n"
        "  enabled: true\n"
        "  mock_rounds_dir: mock_rounds/\n"
        "  mock_round_dir: mock_rounds/\n",  # typo
    )
    with pytest.raises(Exception) as exc:
        load_scenario(tmp_path / "s")
    assert "mock_round_dir" in str(exc.value) or "extra" in str(exc.value).lower()
