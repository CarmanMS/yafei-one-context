"""CLI `onecxt usage-eval daemon-spawn` 子进程测试。

用 subprocess 跑真正的命令——子进程内 fork 不会污染 pytest 进程。
"""
import json
import os
import subprocess
import sys
import time


def _cmd(*args):
    # __main__.py is at one_context/__main__.py (package root, not cli sub-package)
    return [sys.executable, "-m", "one_context", "usage-eval", *args]


def test_cli_daemon_spawn_returns_immediately(tmp_path, monkeypatch):
    """fallback 路径：--session-id 手动调试，无 stdin payload"""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
    repo = tmp_path / "repo"
    repo.mkdir()

    t0 = time.time()
    rc = subprocess.run(
        _cmd("daemon-spawn", "--session-id", "fake-sid", "--cwd", str(repo)),
        timeout=5,
        env={**os.environ, "HOME": str(tmp_path),
             "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES"},
    ).returncode
    elapsed = time.time() - t0
    assert rc == 0
    assert elapsed < 2.0


def test_cli_daemon_spawn_from_stdin(tmp_path, monkeypatch):
    """M-FIX-1 主路径：--from-stdin 读 hook JSON"""
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    transcript = tmp_path / "fake.jsonl"
    transcript.write_text('{"type":"user","message":{"content":"hi"}}\n')
    payload = json.dumps({
        "session_id": "abcd1234-fake",
        "transcript_path": str(transcript),
        "cwd": str(repo),
        "hook_event_name": "SessionEnd",
        "reason": "prompt_input_exit",
    })

    t0 = time.time()
    proc = subprocess.run(
        _cmd("daemon-spawn", "--from-stdin"),
        input=payload, text=True, timeout=5,
        env={**os.environ, "HOME": str(tmp_path),
             "OBJC_DISABLE_INITIALIZE_FORK_SAFETY": "YES"},
    )
    assert proc.returncode == 0
    assert time.time() - t0 < 2.0


def test_cli_daemon_spawn_rejects_no_sid_and_no_stdin(tmp_path, monkeypatch):
    """既无 --from-stdin 也无 --session-id → exit 2 + 报错"""
    monkeypatch.setenv("HOME", str(tmp_path))
    proc = subprocess.run(
        _cmd("daemon-spawn"),
        capture_output=True, text=True, timeout=5,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert proc.returncode == 2
    assert "missing session_id" in proc.stderr


def test_cli_daemon_spawn_rejects_invalid_stdin_json(tmp_path, monkeypatch):
    """--from-stdin 但 stdin 不是 JSON → exit 2"""
    monkeypatch.setenv("HOME", str(tmp_path))
    proc = subprocess.run(
        _cmd("daemon-spawn", "--from-stdin"),
        input="not-json-at-all", text=True,
        capture_output=True, timeout=5,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert proc.returncode == 2
    assert "not JSON" in proc.stderr
