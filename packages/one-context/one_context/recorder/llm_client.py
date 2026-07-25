"""Lightweight LLM client for recorder draft generation (Phase 2.8 M3).

Mirrors `one_context.eval.judge._spawn_judge` to keep the gateway /
permissions / settings story uniform between replay-judge and recorder-
finalize, but trims out the rubric-specific JSON parsing and caching
(finalize is a one-shot per-session call, not a repeatable judge).

Test contract
-------------

Unit tests monkeypatch `call_llm_for_draft` directly (it's a module-
level function so `monkeypatch.setattr` works without touching the
spawn internals). Real LLM calls (M6 wall-clock e2e) drive the real
function which spawns `claude -p`.

`LLMCallError` wraps any spawn / parse failure with a single message
suitable for surfacing to the user via the finalize tool reply (the
finalize flow degrades to a placeholder markdown and persists the raw
error to `staging/llm_error.txt`).
"""

from __future__ import annotations

import os
import subprocess

from one_context.eval.settings_resolver import (
    ModelResolveError,
    resolve_effective_model,
)

DEFAULT_LLM_TIMEOUT_SEC = 240  # finalize draft is one ~3-5k-token output


class LLMCallError(RuntimeError):
    """Raised when the recorder cannot get a draft from the LLM.

    finalize catches this, writes `staging/llm_error.txt`, and returns a
    degraded markdown placeholder so the user can decide whether to
    retry or hand-author the candidate list. The session stays in
    `finalizing` state (per design §6.3 LLMDraftFailure handling).
    """


def _resolve_settings_path() -> str | None:
    """Reuse judge.py's `--settings` resolution so both share the gateway."""
    DEFAULT_SETTINGS_PATH = (
        f"{os.environ.get('HOME', '')}/.claude/settings.json.backup.20260529_153816"
    )
    disable_default = (
        os.environ.get("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT") == "1"
    )
    settings_path = os.environ.get("ONECXT_CLAUDE_SETTINGS")
    if settings_path is None and not disable_default:
        settings_path = DEFAULT_SETTINGS_PATH
    return settings_path or None


def _spawn(prompt: str, model: str, timeout_sec: int) -> str:
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--permission-mode", "bypassPermissions",
    ]
    settings_path = _resolve_settings_path()
    if settings_path:
        cmd.extend(["--settings", settings_path])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as e:
        raise LLMCallError(f"`claude` CLI not found on PATH: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise LLMCallError(
            f"`claude -p` timed out after {timeout_sec}s while generating "
            f"finalize draft (model={model})"
        ) from e
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:500]
        raise LLMCallError(
            f"`claude -p` exited {result.returncode}: {stderr}"
        )
    out = (result.stdout or "").strip()
    if not out:
        raise LLMCallError("`claude -p` returned empty stdout")
    return out


def call_llm_for_draft(
    prompt: str,
    *,
    model: str | None = None,
    timeout_sec: int = DEFAULT_LLM_TIMEOUT_SEC,
) -> str:
    """Run one prompt → string completion. Raises `LLMCallError` on failure.

    Model resolution mirrors the eval/judge path via
    :func:`one_context.eval.settings_resolver.resolve_effective_model` —
    precedence is ``ONECXT_MODEL_OVERRIDE`` env > caller-supplied ``model``
    > ``ONECXT_RECORDER_LLM_MODEL`` env > settings.json
    ``env.ANTHROPIC_MODEL``. The recorder/eval gateway must agree on
    model name + settings file to route correctly through CCD2.
    """
    yaml_model = model or os.environ.get("ONECXT_RECORDER_LLM_MODEL") or None
    try:
        resolved = resolve_effective_model(
            yaml_model=yaml_model,
            settings_path=_resolve_settings_path(),
        )
    except ModelResolveError as e:
        raise LLMCallError(str(e)) from e
    return _spawn(prompt, resolved.model, timeout_sec)


__all__ = [
    "DEFAULT_LLM_TIMEOUT_SEC",
    "LLMCallError",
    "call_llm_for_draft",
]
