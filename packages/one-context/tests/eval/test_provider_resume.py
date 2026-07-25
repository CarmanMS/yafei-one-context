"""provider.run_provider — resume_session_id flag passthrough (Stage 2.7.C.1b).

Mocks subprocess.run so we can inspect the argv the Node provider would
receive without actually spawning node/claude.

The Node side (claude-code.js) will be wired up in Stage 2.7.C.2 — this
test only locks the Python → Node contract: when the runner passes
`resume_session_id`, provider.py must append `--resume-session-id <id>`
to the cmd.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class _FakeProc:
    """Minimal stub of CompletedProcess used by run_provider."""
    def __init__(self):
        self.returncode = 0
        # Provider parses the last non-empty line as JSON.
        self.stdout = (
            '{"text":"ok","tool_calls":[],"init":null,"result":null,'
            '"duration_ms":1,"exit_code":0,"requested_model":"m",'
            '"actual_model":"m","cost_usd":0.0}\n'
        )
        self.stderr = ""


def _capture_cmd(monkeypatch: pytest.MonkeyPatch, **kwargs) -> list[str]:
    """Patch subprocess.run, call run_provider with kwargs, return captured cmd."""
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kw):  # noqa: ARG001
        captured["cmd"] = list(cmd)
        return _FakeProc()

    from one_context.eval import provider as P
    monkeypatch.setattr(P.subprocess, "run", fake_run)

    # provider.run_provider expects a real script path at repo_root/evals/
    # providers/claude-code.js. Stub the file existence check by creating
    # a fake repo root with the script present.
    repo_root = Path(kwargs.pop("_repo_root"))
    (repo_root / "evals" / "providers").mkdir(parents=True, exist_ok=True)
    (repo_root / "evals" / "providers" / "claude-code.js").write_text(
        "// stub", encoding="utf-8"
    )

    defaults = dict(
        repo_root=repo_root,
        query="q",
        cwd=repo_root,
        model="claude-opus-4-7",
        permission_mode="bypassPermissions",
        timeout_ms=1000,
        stream_path=repo_root / "stream.jsonl",
    )
    defaults.update(kwargs)

    P.run_provider(**defaults)
    return captured["cmd"]


def test_provider_omits_resume_flag_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without resume_session_id, cmd must NOT contain --resume-session-id.

    Critical for v1-compat: scenarios that don't enable session_inject
    keep the old `--no-session-persistence` semantics in claude-code.js.
    """
    cmd = _capture_cmd(monkeypatch, _repo_root=tmp_path)
    assert "--resume-session-id" not in cmd


def test_provider_appends_resume_flag_when_id_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cmd = _capture_cmd(
        monkeypatch,
        _repo_root=tmp_path,
        resume_session_id="d880d7a9-d722-45a5-b68e-8fb4b086be4c",
    )
    assert "--resume-session-id" in cmd
    idx = cmd.index("--resume-session-id")
    assert cmd[idx + 1] == "d880d7a9-d722-45a5-b68e-8fb4b086be4c"


def test_provider_resume_flag_position_after_stream_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--resume-session-id should appear AFTER the always-present flags so
    claude-code.js's parseArgs sees the full argv in stable order. This
    locks order for the Node parser contract."""
    cmd = _capture_cmd(
        monkeypatch, _repo_root=tmp_path, resume_session_id="abc",
    )
    assert cmd.index("--stream-path") < cmd.index("--resume-session-id")
