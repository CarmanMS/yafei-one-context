"""Resolve the effective model for provider + judge spawn (Stage 2.X.3).

Single source of truth for "what model name do we actually pass to claude".

Resolution order (highest precedence first):
  1. ``$ONECXT_MODEL_OVERRIDE`` env var — last-resort runtime override (debug)
  2. ``scenario.provider.model`` — explicit per-scenario yaml value, if set
  3. ``settings.json.env.ANTHROPIC_MODEL`` — read from the settings file
     referenced by :func:`one_context.eval.judge._resolve_settings_path`

If all three are absent / unreadable we raise ``ModelResolveError`` with an
explanation pointing the operator at the fix.

Why settings.json drives this:
  The local ``claude`` gateway routes by model name. CCD2 (the project
  default settings) speaks Kimi-K2.6 / K2.5; another settings file might
  speak GLM-5.1. The model is part of the *gateway configuration*, not the
  scenario, so the scenario should be silent by default and let the
  settings decide.

The resolver also returns the *source* of the final value so ``run.json``
can record provenance for the diff layer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedModel:
    model: str
    source: str  # "env_override" | "yaml" | "settings"


class ModelResolveError(RuntimeError):
    """Could not determine an effective model. Message tells operator how to fix."""


def _read_settings_model(settings_path: str | Path | None) -> str | None:
    """Return ``env.ANTHROPIC_MODEL`` from a settings.json, or None if absent."""
    if not settings_path:
        return None
    p = Path(settings_path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    env = data.get("env") if isinstance(data, dict) else None
    if not isinstance(env, dict):
        return None
    val = env.get("ANTHROPIC_MODEL")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def resolve_effective_model(
    yaml_model: str | None,
    settings_path: str | Path | None,
) -> ResolvedModel:
    """Resolve the model name to pass to ``claude -p --model <X>``.

    Precedence: env override > yaml value > settings.json env.ANTHROPIC_MODEL.
    """
    env_override = os.environ.get("ONECXT_MODEL_OVERRIDE")
    if env_override and env_override.strip():
        return ResolvedModel(model=env_override.strip(), source="env_override")

    if yaml_model and yaml_model.strip():
        return ResolvedModel(model=yaml_model.strip(), source="yaml")

    settings_model = _read_settings_model(settings_path)
    if settings_model:
        return ResolvedModel(model=settings_model, source="settings")

    raise ModelResolveError(
        "no model name available — set one of:\n"
        "  - `provider.model:` in scenario.yaml (per-scenario)\n"
        f"  - `env.ANTHROPIC_MODEL` in {settings_path or '<settings.json>'}\n"
        "  - `$ONECXT_MODEL_OVERRIDE` env var (one-off debug override)\n"
        "model is gateway-coupled (see settings.json), so the recommended "
        "long-term fix is the settings.json env field."
    )
