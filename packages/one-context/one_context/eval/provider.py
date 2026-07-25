"""Python wrapper around `evals/providers/claude-code.js`.

Spawns the Node provider, parses its single-line JSON result.

Per ISS-019 / Stage 1.1.8, the provider *never raises* for normal failure
modes — it returns a ``ProviderResult`` with ``provider_status`` set to
one of ``api_error`` / ``timeout`` / ``empty_stdout`` / ``other``.
``KeyboardInterrupt`` is intentionally **not** caught here; the runner
layer catches it and assembles its own ``ProviderResult``. Only true
configuration errors (e.g. missing provider script) raise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Provider status enum (string literal, kept loose to stay JSON-friendly).
PROVIDER_STATUS_OK = "ok"
PROVIDER_STATUS_API_ERROR = "api_error"
PROVIDER_STATUS_TIMEOUT = "timeout"
PROVIDER_STATUS_INTERRUPTED = "interrupted"
PROVIDER_STATUS_EMPTY_STDOUT = "empty_stdout"
PROVIDER_STATUS_OTHER = "other"


@dataclass
class ProviderResult:
    ok: bool
    exit_code: int
    duration_ms: int
    requested_model: str
    actual_model: str | None
    final_text: str
    tool_calls: list[dict[str, Any]]
    stream_path: str | None
    provider_status: str = PROVIDER_STATUS_OK
    cost_usd: float = 0.0
    timeout: bool = False
    stderr_tail: str = ""
    raw: dict[str, Any] | None = None


def _provider_script(repo_root: Path) -> Path:
    return repo_root / "evals" / "providers" / "claude-code.js"


def _read_last_result_line(stream_path: Path) -> dict[str, Any] | None:
    """Return the last ``{type: 'result', ...}`` line from stream-json, if any.

    Tolerates partial files (provider crashed mid-stream) and unparseable
    lines.
    """
    if not stream_path or not Path(stream_path).is_file():
        return None
    last: dict[str, Any] | None = None
    try:
        with Path(stream_path).open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("type") == "result":
                    last = obj
    except OSError:
        return None
    return last


def extract_cost_usd(stream_path: Path | str | None) -> float:
    """Extract ``total_cost_usd`` from the last result line of stream-json.

    Returns 0.0 when the file is missing, has no result line, or the value
    cannot be parsed as float. Safe to call after provider failure.
    """
    if stream_path is None:
        return 0.0
    sp = Path(stream_path) if not isinstance(stream_path, Path) else stream_path
    obj = _read_last_result_line(sp)
    if obj is None:
        return 0.0
    val = obj.get("total_cost_usd")
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _stderr_tail(text: str | None, max_bytes: int = 2000) -> str:
    if not text:
        return ""
    s = str(text)
    if len(s) <= max_bytes:
        return s
    return s[-max_bytes:]


def _classify_api_error(raw: dict[str, Any], stream_path: Path) -> bool:
    """Heuristic: provider exited normally but content indicates API error."""
    if bool(raw.get("is_error", False)):
        return True
    final_text = str(raw.get("final_text", "") or "")
    if "API Error" in final_text:
        return True
    # Fall back: peek at the stream-json result line directly.
    last = _read_last_result_line(stream_path)
    if last is not None and bool(last.get("is_error", False)):
        return True
    return False


def run_provider(
    *,
    repo_root: Path,
    query: str,
    cwd: Path,
    model: str,
    permission_mode: str,
    timeout_ms: int,
    stream_path: Path,
    resume_session_id: str | None = None,
    disallowed_tools: list[str] | None = None,
) -> ProviderResult:
    script = _provider_script(repo_root)
    if not script.is_file():
        raise FileNotFoundError(f"provider script missing: {script}")

    node_bin = shutil.which("node") or "node"
    cmd = [
        node_bin,
        str(script),
        "--query", query,
        "--cwd", str(cwd),
        "--model", model,
        "--permission-mode", permission_mode,
        "--timeout-ms", str(timeout_ms),
        "--stream-path", str(stream_path),
    ]
    # ISS-024 / Stage 2.7.C: when the runner has forged a session jsonl,
    # tell the Node provider to start cc with `--resume <id>` so the
    # forged history loads. claude-code.js MUST drop
    # `--no-session-persistence` in this mode (it conflicts with --resume).
    # See tech_design.md §6.
    if resume_session_id:
        cmd.extend(["--resume-session-id", resume_session_id])
    # M5: cc-side escape防御 (P3 双保险 outer ring). When session_inject
    # is active, the runner derives the set of mocked tool names and
    # passes them here; provider.js appends `--disallowedTools <csv>`
    # so cc REFUSES to invoke the real tool even if it tries to escape
    # the forged history. See recording-mode-design.md §12.3.
    if disallowed_tools:
        cmd.extend(["--disallowed-tools", ",".join(disallowed_tools)])
    # Allow ample wall time on top of provider timeoutMs so we capture
    # crash output even if the provider's own timer fires.
    proc_timeout = (timeout_ms / 1000) + 30

    started_at = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=proc_timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        # TimeoutExpired carries captured output up to the kill point.
        stderr_partial = ""
        if getattr(e, "stderr", None):
            stderr_partial = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="replace")
        return ProviderResult(
            ok=False,
            exit_code=-1,
            duration_ms=duration_ms or int(timeout_ms),
            requested_model=model,
            actual_model=None,
            final_text="",
            tool_calls=[],
            stream_path=str(stream_path),
            provider_status=PROVIDER_STATUS_TIMEOUT,
            cost_usd=extract_cost_usd(stream_path),
            timeout=True,
            stderr_tail=_stderr_tail(stderr_partial),
            raw=None,
        )
    # KeyboardInterrupt deliberately not caught — runner catches it.

    # Empty stdout: provider produced nothing usable.
    if not proc.stdout or not proc.stdout.strip():
        return ProviderResult(
            ok=False,
            exit_code=int(proc.returncode),
            duration_ms=0,
            requested_model=model,
            actual_model=None,
            final_text="",
            tool_calls=[],
            stream_path=str(stream_path),
            provider_status=PROVIDER_STATUS_EMPTY_STDOUT,
            cost_usd=extract_cost_usd(stream_path),
            timeout=False,
            stderr_tail=_stderr_tail(proc.stderr),
            raw=None,
        )

    # Parse the last non-empty stdout line as the aggregated provider JSON.
    try:
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        raw = json.loads(lines[-1])
        if not isinstance(raw, dict):
            raise ValueError(f"provider result is not a JSON object: {type(raw).__name__}")
    except (json.JSONDecodeError, ValueError, IndexError) as e:
        return ProviderResult(
            ok=False,
            exit_code=int(proc.returncode),
            duration_ms=0,
            requested_model=model,
            actual_model=None,
            final_text="",
            tool_calls=[],
            stream_path=str(stream_path),
            provider_status=PROVIDER_STATUS_OTHER,
            cost_usd=extract_cost_usd(stream_path),
            timeout=False,
            stderr_tail=_stderr_tail(
                (proc.stderr or "")
                + ("\n[parse-error] " + str(e) if str(e) else "")
            ),
            raw=None,
        )

    # API error detection (stream-json is_error or final_text marker).
    if _classify_api_error(raw, stream_path):
        return ProviderResult(
            ok=False,
            exit_code=int(raw.get("exit_code", proc.returncode)),
            duration_ms=int(raw.get("duration_ms", 0)),
            requested_model=str(raw.get("requested_model", model)),
            actual_model=raw.get("actual_model"),
            final_text=str(raw.get("final_text", "")),
            tool_calls=list(raw.get("tool_calls", [])),
            stream_path=raw.get("stream_path") or str(stream_path),
            provider_status=PROVIDER_STATUS_API_ERROR,
            cost_usd=extract_cost_usd(stream_path),
            timeout=bool(raw.get("timeout", False)),
            stderr_tail=_stderr_tail(raw.get("stderr_tail") or proc.stderr),
            raw=raw,
        )

    # Provider-reported timeout (handled via aggregated JSON, not Python TimeoutExpired).
    if bool(raw.get("timeout", False)):
        return ProviderResult(
            ok=False,
            exit_code=int(raw.get("exit_code", proc.returncode)),
            duration_ms=int(raw.get("duration_ms", 0)),
            requested_model=str(raw.get("requested_model", model)),
            actual_model=raw.get("actual_model"),
            final_text=str(raw.get("final_text", "")),
            tool_calls=list(raw.get("tool_calls", [])),
            stream_path=raw.get("stream_path") or str(stream_path),
            provider_status=PROVIDER_STATUS_TIMEOUT,
            cost_usd=extract_cost_usd(stream_path),
            timeout=True,
            stderr_tail=_stderr_tail(raw.get("stderr_tail") or proc.stderr),
            raw=raw,
        )

    ok_flag = bool(raw.get("ok", False))
    if not ok_flag:
        # Provider reported not-ok with no recognizable reason — bucket as "other".
        return ProviderResult(
            ok=False,
            exit_code=int(raw.get("exit_code", proc.returncode)),
            duration_ms=int(raw.get("duration_ms", 0)),
            requested_model=str(raw.get("requested_model", model)),
            actual_model=raw.get("actual_model"),
            final_text=str(raw.get("final_text", "")),
            tool_calls=list(raw.get("tool_calls", [])),
            stream_path=raw.get("stream_path") or str(stream_path),
            provider_status=PROVIDER_STATUS_OTHER,
            cost_usd=extract_cost_usd(stream_path),
            timeout=False,
            stderr_tail=_stderr_tail(raw.get("stderr_tail") or proc.stderr),
            raw=raw,
        )

    # Success path.
    return ProviderResult(
        ok=True,
        exit_code=int(raw.get("exit_code", 0)),
        duration_ms=int(raw.get("duration_ms", 0)),
        requested_model=str(raw.get("requested_model", model)),
        actual_model=raw.get("actual_model"),
        final_text=str(raw.get("final_text", "")),
        tool_calls=list(raw.get("tool_calls", [])),
        stream_path=raw.get("stream_path") or str(stream_path),
        provider_status=PROVIDER_STATUS_OK,
        cost_usd=extract_cost_usd(stream_path),
        timeout=False,
        stderr_tail=_stderr_tail(raw.get("stderr_tail", "")),
        raw=raw,
    )
