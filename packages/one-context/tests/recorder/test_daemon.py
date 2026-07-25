"""Live-trace daemon tests.

Covers `recorder/daemon.py`:

- spawn → daemon.json written, port bound, all endpoints respond
- GET / → 302 to /report.html
- GET /report.html contains the Live tab
- GET /api/rounds.json returns parsed jsonl
- GET /api/status.json reflects round count & status
- POST /api/stop terminates the server
- stop_daemon kills a pid + removes daemon.json
- stop_daemon on missing pid: no-op, returns False, file removed
- list_daemons reports alive/dead correctly
- purge_dead_daemons removes only dead entries
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
from pathlib import Path

import pytest

from one_context.recorder import daemon as d
from one_context.recorder.session import start_session


def _get(url: str, timeout: float = 2.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""


def _post(url: str, timeout: float = 2.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""


def _wait_until(predicate, timeout=3.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _append_jsonl(session_dir: Path, records: list[dict]) -> None:
    with (session_dir / "rounds.jsonl").open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_spawn_writes_daemon_json_and_serves(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    try:
        info = d.spawn_daemon(sess.session_id)
        assert info["session_id"] == sess.session_id
        assert info["pid"] > 0
        assert info["port"] > 0
        url = info["url"]

        # GET / → 302 to /report.html (urlopen follows, gives 200)
        code, body = _get(url)
        assert code == 200
        assert b"Live" in body or b"live" in body

        # GET /report.html directly
        code, body = _get(url + "report.html")
        assert code == 200
        assert b"recordingReport()" in body
        # Live tab marker
        assert b"tab === 'live'" in body or b'tab===\'live\'' in body

        # Initially no rounds
        code, body = _get(url + "api/rounds.json")
        assert code == 200
        assert json.loads(body) == []

        # Status reflects session
        code, body = _get(url + "api/status.json")
        assert code == 200
        status = json.loads(body)
        assert status["session_id"] == sess.session_id
        assert status["status"] == "recording"
        assert status["round_count"] == 0

        # Append a round to jsonl, status & rounds endpoint should reflect it
        _append_jsonl(Path(sess.recording_dir), [{
            "round_id": "round-01-bash-deadbeef",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_result": "ok\n",
            "boundary_type": "local_tool",
            "event_type": "PostToolUse",
            "cc_session_id": "cc-target",
        }])
        code, body = _get(url + "api/rounds.json")
        rounds = json.loads(body)
        assert len(rounds) == 1
        assert rounds[0]["tool_name"] == "Bash"
        assert rounds[0]["seq"] == 1
        code, body = _get(url + "api/status.json")
        status = json.loads(body)
        assert status["round_count"] == 1
        assert status["current_tool"] == "Bash"
    finally:
        d.stop_daemon(sess.session_id)


def test_post_stop_shuts_down(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    info = d.spawn_daemon(sess.session_id)
    pid = info["pid"]
    url = info["url"]

    code, body = _post(url + "api/stop")
    assert code == 200
    assert _wait_until(lambda: not d._pid_alive(pid), timeout=3.0)
    assert not (Path(sess.recording_dir) / "daemon.json").exists()


def test_stop_daemon_kills_and_cleans(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    info = d.spawn_daemon(sess.session_id)
    pid = info["pid"]
    assert d._pid_alive(pid)
    ok = d.stop_daemon(sess.session_id)
    assert ok is True
    assert not d._pid_alive(pid)
    assert not (Path(sess.recording_dir) / "daemon.json").exists()


def test_stop_daemon_handles_dead_pid(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    # Fake a stale daemon.json pointing at a pid that's definitely gone.
    (Path(sess.recording_dir) / "daemon.json").write_text(json.dumps({
        "session_id": sess.session_id,
        "pid": 999999,
        "port": 1,
        "url": "http://127.0.0.1:1/",
        "started_at": "2026-06-03T00:00:00+00:00",
    }), encoding="utf-8")
    ok = d.stop_daemon(sess.session_id)
    assert ok is False  # nothing alive to stop
    assert not (Path(sess.recording_dir) / "daemon.json").exists()


def test_list_and_purge_dead_daemons(
    recorder_tmp: Path, repo_with_skill: Path,
) -> None:
    sess_live = start_session(
        "demo", "live-scn", cc_session_id="cc-target", repo_root=repo_with_skill,
    )
    info = d.spawn_daemon(sess_live.session_id)
    try:
        # Plant a fake dead daemon manually for a second session id.
        dead_sid = "deadbeef-dead-dead-dead-deaddeaddead"
        dead_dir = recorder_tmp / dead_sid
        dead_dir.mkdir(parents=True)
        (dead_dir / "daemon.json").write_text(json.dumps({
            "session_id": dead_sid, "pid": 999999, "port": 1,
            "url": "http://127.0.0.1:1/", "started_at": "2026-06-03T00:00:00+00:00",
        }), encoding="utf-8")

        rows = d.list_daemons()
        by_sid = {r["session_id"]: r for r in rows}
        assert by_sid[sess_live.session_id]["alive"] is True
        assert by_sid[dead_sid]["alive"] is False

        n = d.purge_dead_daemons()
        assert n == 1
        # live one untouched
        assert (Path(sess_live.recording_dir) / "daemon.json").exists()
        # dead one gone
        assert not (dead_dir / "daemon.json").exists()
    finally:
        d.stop_daemon(sess_live.session_id)


def test_pick_free_port_returns_bindable(recorder_tmp: Path) -> None:
    port = d._pick_free_port()
    # Verify we can immediately rebind it (the kernel does not hold it long).
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.close()
