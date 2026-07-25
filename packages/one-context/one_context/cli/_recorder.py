"""`onecxt recorder ...` CLI subcommands.

Today only manages the live-trace daemon (start/stop is via the MCP
tool; this surface is for human-facing inspection + cleanup):

    onecxt recorder list-daemons
    onecxt recorder stop-live <session_id>
    onecxt recorder stop-live --all
    onecxt recorder stop-live --current
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _cmd_recorder_list_daemons(_root: Path, _args: argparse.Namespace) -> int:
    from one_context.recorder import daemon as d
    rows = d.list_daemons()
    if not rows:
        print("No recorder daemons found.")
        return 0
    print(f"{'PID':>7}  {'PORT':>5}  {'ALIVE':>5}  SESSION_ID")
    for r in rows:
        alive = "yes" if r.get("alive") else "no"
        print(
            f"{r.get('pid', 0):>7}  {r.get('port', 0):>5}  {alive:>5}  "
            f"{r.get('session_id', '?')}  -> {r.get('url', '')}"
        )
    return 0


def _cmd_recorder_stop_live(_root: Path, args: argparse.Namespace) -> int:
    from one_context.recorder import daemon as d
    from one_context.recorder.session import get_active_session_id

    if args.all:
        targets = [r["session_id"] for r in d.list_daemons() if r.get("session_id")]
    elif args.current:
        sid = get_active_session_id()
        if not sid:
            print("No active recording session.")
            return 0
        targets = [sid]
    elif args.session_id:
        targets = [args.session_id]
    else:
        print("error: one of <session_id> / --all / --current is required")
        return 2

    stopped = 0
    for sid in targets:
        ok = d.stop_daemon(sid)
        marker = "✓ stopped" if ok else "· already dead (file removed)"
        print(f"{marker}: {sid}")
        if ok:
            stopped += 1
    print(f"\nstopped {stopped}/{len(targets)} daemon(s).")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "recorder",
        help="Manage the recording live-trace daemon",
        description="Inspect / stop the per-session HTTP daemon spawned by start_recording.",
    )
    rsub = p.add_subparsers(dest="recorder_command", required=True)

    p_list = rsub.add_parser("list-daemons", help="list known daemon.json files + liveness")
    p_list.set_defaults(func=_cmd_recorder_list_daemons)

    p_stop = rsub.add_parser("stop-live", help="stop a daemon (SIGTERM + SIGKILL fallback)")
    g = p_stop.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="stop every daemon found")
    g.add_argument("--current", action="store_true", help="stop the daemon of the currently-active recording session")
    p_stop.add_argument("session_id", nargs="?", help="explicit session id (uuid)")
    p_stop.set_defaults(func=_cmd_recorder_stop_live)
