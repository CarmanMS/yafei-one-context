"""Stage 2.X.1 smoke test for evals/providers/claude-code.js.

We don't run the full provider (it spawns claude); we just exercise the
JS file's argument-parsing + settings-resolution path by invoking node
with a tiny harness that requires the module's parseArgs-like behavior
indirectly via `--help`-style smoke.

Cheaper / more robust: assert the spawned cliArgs list by grepping the
JS source for the new --settings injection block. This locks the
contract without paying node-test infra cost.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PROVIDER_JS = REPO_ROOT / "evals" / "providers" / "claude-code.js"


def test_provider_js_contains_settings_injection() -> None:
    """Lock the Stage 2.X.1 contract via source grep — guards against silent removal."""
    src = PROVIDER_JS.read_text(encoding="utf-8")
    assert "ONECXT_CLAUDE_SETTINGS" in src, "env var name must be referenced"
    assert "ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT" in src, "disable-default escape hatch must exist"
    assert "settings.json.backup.20260529_153816" in src, "CCD2 default path must be hard-coded"
    assert "cliArgs.push('--settings'" in src, "--settings must be appended to cliArgs"


def test_provider_js_default_path_uses_home() -> None:
    """Default path must be HOME-relative so it works for any user's homedir."""
    src = PROVIDER_JS.read_text(encoding="utf-8")
    # The default-path line should interpolate $HOME.
    assert "process.env.HOME" in src, "default settings path must use HOME env var"


# ── Stage 2.7.C.2: --resume-session-id (session inject) ────────────────────


def test_provider_js_parses_resume_session_id_flag() -> None:
    """parseArgs must recognise --resume-session-id (otherwise it dies as
    'unknown arg' and the Python runner's session inject silently breaks)."""
    src = PROVIDER_JS.read_text(encoding="utf-8")
    assert "'--resume-session-id'" in src, \
        "parseArgs case for --resume-session-id missing"
    assert "args.resumeSessionId" in src, \
        "parsed value must land in args.resumeSessionId"


def test_provider_js_appends_resume_to_cli_args() -> None:
    """When args.resumeSessionId is truthy, cliArgs must include --resume <id>
    so cc loads the forged session jsonl. Without this push, the runner
    creates the forged file but cc doesn't read it — invisible breakage."""
    src = PROVIDER_JS.read_text(encoding="utf-8")
    assert "cliArgs.push('--resume', args.resumeSessionId)" in src, \
        "spawn must add --resume <id> when resumeSessionId is set"


def test_provider_js_resume_block_is_guarded_by_truthy_check() -> None:
    """The --resume push must be inside an `if (args.resumeSessionId)` guard;
    otherwise sessions with NO session inject would get `--resume undefined`
    and cc would barf."""
    src = PROVIDER_JS.read_text(encoding="utf-8")
    # Look for the guarded structure (allow whitespace variance).
    import re
    pattern = re.compile(
        r"if\s*\(\s*args\.resumeSessionId\s*\)\s*\{[^}]*cliArgs\.push\(\s*'--resume'",
        re.DOTALL,
    )
    assert pattern.search(src), \
        "--resume push must be wrapped in `if (args.resumeSessionId)` guard"
