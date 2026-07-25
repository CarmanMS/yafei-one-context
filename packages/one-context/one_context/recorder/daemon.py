"""Recording live-trace HTTP daemon.

Forked by `start_recording` to serve a live, refreshing dashboard of the
recording in progress. The daemon detaches from the mcp process so it
survives past mcp's short RPC lifetime, and is killed only by the user
via `onecxt recorder stop-live <sid>` (or machine restart).

Run directly:

    python -m one_context.recorder.daemon <session_id>

Or use `spawn_daemon(session_id)` from inside mcp_server.py.

Endpoints:

    GET  /                   → 302 → /report.html
    GET  /report.html        → jinja-rendered report (re-renders per request)
    GET  /api/rounds.json    → parsed rounds.jsonl as JSON array
    GET  /api/status.json    → live status: round_count, last_round_ts, etc.
    POST /api/stop           → graceful shutdown (CLI uses this)

Lifecycle / ownership: one daemon per session, bound to session_dir. The
daemon is **NOT** killed by finalize / commit_finalize / abort — the
user keeps the dashboard alive as long as they want. Stale daemons are
swept by `purge_dead_daemons()` (called at start_recording entry).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

from one_context.recorder.session import (
    SessionNotFound,
    load_session,
    recorder_root,
)


# ── pid file (daemon.json) helpers ─────────────────────────────────────


def _daemon_file(session_id: str) -> Path:
    return recorder_root() / session_id / "daemon.json"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def read_daemon_info(session_id: str) -> Optional[dict]:
    f = _daemon_file(session_id)
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── spawn (called by mcp_server) ──────────────────────────────────────


def _pick_free_port() -> int:
    """Ask the OS for a free port and immediately release it.

    Small race: another process could grab the port between this call
    and the HTTPServer bind. In practice fine on a single-user dev box;
    the server bind retries with a new port on EADDRINUSE.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def spawn_daemon(session_id: str) -> dict:
    """Fork a detached daemon serving session_id; return its info dict.

    Idempotent: if a live daemon already serves this session, return its
    existing daemon.json without spawning a second one.
    """
    existing = read_daemon_info(session_id)
    if existing and _pid_alive(int(existing.get("pid", 0))):
        return existing

    # stale → remove before spawn
    if existing is not None:
        try:
            _daemon_file(session_id).unlink()
        except OSError:
            pass

    # Make sure session exists before we fork (avoids zombie daemon for
    # an invalid session_id).
    load_session(session_id)

    # Spawn `python -m one_context.recorder.daemon <sid>` detached.
    log_path = recorder_root() / session_id / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fd = open(log_path, "ab")  # noqa: SIM115 — owned by child after start_new_session
    proc = subprocess.Popen(
        [sys.executable, "-m", "one_context.recorder.daemon", session_id],
        stdout=log_fd,
        stderr=log_fd,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # detach from mcp's process group
        close_fds=True,
    )
    # Daemonize the wait so the child does not become a zombie when this
    # parent (mcp/pytest) outlives it. A background thread joins the
    # subprocess and discards its exit status. Without this, _pid_alive
    # would keep returning True for the zombie even after kill, because
    # os.kill(pid, 0) succeeds on entries still in the process table.
    threading.Thread(target=proc.wait, daemon=True).start()

    # Wait briefly for the child to write daemon.json (server bind takes
    # ~50-200ms). Up to 3s before we give up.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        info = read_daemon_info(session_id)
        if info and _pid_alive(int(info.get("pid", 0))):
            return info
        if proc.poll() is not None:
            raise RuntimeError(
                f"daemon for session {session_id!r} exited "
                f"immediately (code={proc.returncode}); see {log_path}"
            )
        time.sleep(0.05)
    raise RuntimeError(
        f"daemon for session {session_id!r} did not write daemon.json "
        f"within 3s; see {log_path}"
    )


# ── stop / cleanup ────────────────────────────────────────────────────


def stop_daemon(session_id: str, *, timeout: float = 3.0) -> bool:
    """SIGTERM then SIGKILL fallback. Returns True if a daemon was stopped.

    Safe to call when daemon.json is stale (pid gone) — just deletes the
    file and returns False.
    """
    info = read_daemon_info(session_id)
    if info is None:
        return False
    pid = int(info.get("pid", 0))
    f = _daemon_file(session_id)
    if not _pid_alive(pid):
        try:
            f.unlink()
        except OSError:
            pass
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        try:
            f.unlink()
        except OSError:
            pass
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.05)
    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        # Wait briefly for SIGKILL to take effect (kernel reaps async).
        kill_deadline = time.monotonic() + 1.0
        while time.monotonic() < kill_deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.02)
    try:
        f.unlink()
    except OSError:
        pass
    return True


def list_daemons() -> list[dict]:
    """Scan recorder_root for daemon.json; mark each alive/dead."""
    root = recorder_root()
    out: list[dict] = []
    if not root.is_dir():
        return out
    for sdir in sorted(root.iterdir()):
        if not sdir.is_dir():
            continue
        f = sdir / "daemon.json"
        if not f.is_file():
            continue
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        info["alive"] = _pid_alive(int(info.get("pid", 0)))
        out.append(info)
    return out


def purge_dead_daemons() -> int:
    """Remove daemon.json files whose pid is no longer alive. Returns count."""
    n = 0
    for info in list_daemons():
        if info.get("alive"):
            continue
        sid = info.get("session_id")
        if not sid:
            continue
        try:
            _daemon_file(sid).unlink()
            n += 1
        except OSError:
            continue
    return n


# ── HTTP server ────────────────────────────────────────────────────────


class _ReportHandler(BaseHTTPRequestHandler):
    server_version = "OnecxtRecorderDaemon/1.0"
    session_id: str = ""  # set by serve_forever wrapper

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # Quiet by default; uncomment for debugging.
        # sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
        return

    # ── routing ────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/report.html")
            self.end_headers()
            return
        if path == "/report.html":
            return self._serve_report()
        if path == "/api/rounds.json":
            return self._serve_rounds()
        if path == "/api/status.json":
            return self._serve_status()
        self.send_error(404, f"Unknown path: {path}")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/api/stop":
            self._serve_stop()
            return
        self.send_error(404, f"Unknown path: {path}")

    # ── handlers ──────────────────────────────────────────────────

    def _serve_report(self) -> None:
        try:
            from one_context.recorder import report as report_mod
            session = load_session(self.session_id)
            html = report_mod.render_live_html(session)
        except SessionNotFound as e:
            self.send_error(410, f"session gone: {e}")
            return
        except Exception as e:
            self.send_error(500, f"render failed: {e!r}")
            return
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_rounds(self) -> None:
        try:
            session = load_session(self.session_id)
            from one_context.recorder import report as report_mod
            rounds = report_mod.collect_live_rounds(session)
        except SessionNotFound as e:
            self.send_error(410, f"session gone: {e}")
            return
        except Exception as e:
            self.send_error(500, f"rounds read failed: {e!r}")
            return
        body = json.dumps(rounds, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_status(self) -> None:
        try:
            session = load_session(self.session_id)
            from one_context.recorder import report as report_mod
            status = report_mod.collect_live_status(session)
        except SessionNotFound as e:
            self.send_error(410, f"session gone: {e}")
            return
        except Exception as e:
            self.send_error(500, f"status read failed: {e!r}")
            return
        body = json.dumps(status, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_stop(self) -> None:
        # Reply first, then exit the process from a worker thread so the
        # response flushes. We use os._exit rather than a graceful
        # serve_forever shutdown because ThreadingHTTPServer.shutdown
        # can stall waiting on in-flight handler threads (including this
        # one) and the daemon's job is done — just leave.
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        def _bye() -> None:
            # small delay to let the response actually flush over TCP
            time.sleep(0.05)
            # Best-effort clean-up; main's finally block won't run after _exit
            try:
                _daemon_file(self.session_id).unlink()
            except OSError:
                pass
            os._exit(0)

        threading.Thread(target=_bye, daemon=True).start()


def _serve(session_id: str) -> None:
    """Run the http server until SIGTERM or POST /api/stop."""
    # Pick a free port (with one retry if bind races lost).
    for _attempt in range(3):
        port = _pick_free_port()
        try:
            handler = type("Handler", (_ReportHandler,), {"session_id": session_id})
            httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue
    else:
        raise RuntimeError("could not bind any free port after 3 attempts")

    info = {
        "session_id": session_id,
        "pid": os.getpid(),
        "port": port,
        "url": f"http://127.0.0.1:{port}/",
        "started_at": _utc_now_iso(),
    }
    _daemon_file(session_id).write_text(
        json.dumps(info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    def _shutdown(_signum: int, _frame: Any) -> None:
        # Best-effort cleanup, then hard exit. ThreadingHTTPServer.shutdown
        # can stall on in-flight handlers; signals should be immediate.
        try:
            _daemon_file(session_id).unlink()
        except OSError:
            pass
        os._exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        httpd.serve_forever()
    finally:
        # Best-effort cleanup; CLI stop_daemon also unlinks.
        try:
            _daemon_file(session_id).unlink()
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m one_context.recorder.daemon",
        description="Recording live-trace HTTP daemon (do not call directly; use spawn_daemon).",
    )
    parser.add_argument("session_id", help="recording session id (uuid)")
    args = parser.parse_args()
    _serve(args.session_id)


if __name__ == "__main__":
    main()
