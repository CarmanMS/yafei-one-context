"""Stage 2.X.3 — settings_resolver unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.eval.settings_resolver import (
    ModelResolveError,
    ResolvedModel,
    _read_settings_model,
    resolve_effective_model,
)


# ── _read_settings_model ──────────────────────────────────────────────────


def test_read_returns_model_from_well_formed_settings(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "Kimi-K2.6"}}), encoding="utf-8")
    assert _read_settings_model(p) == "Kimi-K2.6"


def test_read_returns_none_when_path_missing(tmp_path: Path) -> None:
    assert _read_settings_model(tmp_path / "nope.json") is None


def test_read_returns_none_when_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert _read_settings_model(p) is None


def test_read_returns_none_when_env_missing(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"other": "field"}), encoding="utf-8")
    assert _read_settings_model(p) is None


def test_read_strips_whitespace_and_rejects_blank(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "   "}}), encoding="utf-8")
    assert _read_settings_model(p) is None
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "  Kimi-K2.6  "}}), encoding="utf-8")
    assert _read_settings_model(p) == "Kimi-K2.6"


def test_read_none_path_returns_none() -> None:
    assert _read_settings_model(None) is None


# ── resolve_effective_model precedence ────────────────────────────────────


def test_env_override_wins_over_yaml_and_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "FromSettings"}}), encoding="utf-8")
    monkeypatch.setenv("ONECXT_MODEL_OVERRIDE", "FromEnv")
    r = resolve_effective_model(yaml_model="FromYaml", settings_path=p)
    assert r == ResolvedModel(model="FromEnv", source="env_override")


def test_yaml_wins_over_settings_when_no_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ONECXT_MODEL_OVERRIDE", raising=False)
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "FromSettings"}}), encoding="utf-8")
    r = resolve_effective_model(yaml_model="FromYaml", settings_path=p)
    assert r == ResolvedModel(model="FromYaml", source="yaml")


def test_settings_used_when_yaml_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ONECXT_MODEL_OVERRIDE", raising=False)
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "Kimi-K2.6"}}), encoding="utf-8")
    r = resolve_effective_model(yaml_model=None, settings_path=p)
    assert r == ResolvedModel(model="Kimi-K2.6", source="settings")


def test_raises_when_all_sources_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ONECXT_MODEL_OVERRIDE", raising=False)
    with pytest.raises(ModelResolveError) as exc:
        resolve_effective_model(yaml_model=None, settings_path=tmp_path / "nope.json")
    msg = str(exc.value)
    # Error message should point operator at the three fix paths.
    assert "scenario.yaml" in msg
    assert "ANTHROPIC_MODEL" in msg
    assert "ONECXT_MODEL_OVERRIDE" in msg


def test_yaml_whitespace_only_treated_as_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ONECXT_MODEL_OVERRIDE", raising=False)
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "FromSettings"}}), encoding="utf-8")
    r = resolve_effective_model(yaml_model="   ", settings_path=p)
    assert r == ResolvedModel(model="FromSettings", source="settings")


def test_env_override_whitespace_only_falls_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONECXT_MODEL_OVERRIDE", "   ")
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "FromSettings"}}), encoding="utf-8")
    r = resolve_effective_model(yaml_model="FromYaml", settings_path=p)
    # whitespace-only env override is ignored → yaml takes over.
    assert r == ResolvedModel(model="FromYaml", source="yaml")
