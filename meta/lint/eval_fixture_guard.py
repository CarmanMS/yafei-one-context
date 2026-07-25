#!/usr/bin/env python3
"""commit-msg hook: warn (non-blocking) when staged diff touches
`features/_evals/` but the commit message lacks the `[eval-fixture]` tag.

ISS-022 / Stage 2.0.3.g. Exits 0 in all cases — warning only.

Usage (commit-msg hook):
    .git/hooks/commit-msg <commit-msg-file>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EVAL_PREFIX = "features/_evals/"
TAG = "[eval-fixture]"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _staged_paths() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line for line in out.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    # commit-msg hook passes the path to COMMIT_EDITMSG as argv[1]; fall
    # back to .git/COMMIT_EDITMSG so the script also works for ad-hoc runs.
    msg_path = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / ".git" / "COMMIT_EDITMSG"
    if not msg_path.is_file():
        return 0

    touched = [p for p in _staged_paths() if p.startswith(EVAL_PREFIX)]
    if not touched:
        return 0

    message = msg_path.read_text(encoding="utf-8", errors="replace")
    if TAG in message:
        return 0

    print(
        f"\033[33m[eval-fixture-guard]\033[0m 检测到 {EVAL_PREFIX} 改动 "
        f"但 commit message 无 {TAG} 标签：",
        file=sys.stderr,
    )
    for p in touched[:10]:
        print(f"  - {p}", file=sys.stderr)
    if len(touched) > 10:
        print(f"  ... 共 {len(touched)} 处", file=sys.stderr)
    print(
        f"  请确认是评测 fixture 的预期修改；若是，请在 commit message 加上 {TAG}\n"
        f"  以便后续审计与 baseline diff 触发。(warn-only, exit 0)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
