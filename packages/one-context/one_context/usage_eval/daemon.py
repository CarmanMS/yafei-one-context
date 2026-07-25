"""double-fork daemon：父立即返回，孙子后台跑 payload + 看门狗超时。

入口 ``double_fork_and_run(payload, log_path, daemon_timeout_sec)``。

- 评审 S-01：daemon 总超时（多 slot 累计上限）与单 slot 5min 解耦。
  支持 env ``ONECXT_USAGE_EVAL_DAEMON_TIMEOUT`` 覆盖（秒）。
- 评审 S-03：macOS fork+subprocess 偶发 ObjC fork-safety abort，
  在调任何 subprocess 前显式关闭 ObjC 初始化检查。
"""
from __future__ import annotations

import logging
import os
import traceback
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

DEFAULT_DAEMON_TIMEOUT_SEC = 1800  # 30min
DAEMON_TIMEOUT_ENV = "ONECXT_USAGE_EVAL_DAEMON_TIMEOUT"


def _resolve_daemon_timeout(default: int) -> int:
    raw = os.environ.get(DAEMON_TIMEOUT_ENV, "").strip()
    if not raw:
        return default
    try:
        return max(60, int(raw))
    except ValueError:
        return default


def double_fork_and_run(
    payload: Callable[[], None],
    *,
    log_path: Path | None = None,
    daemon_timeout_sec: int = DEFAULT_DAEMON_TIMEOUT_SEC,
) -> int:
    """double-fork + setsid 后台跑 payload；父立即返回 0。

    timeout 是**整个 daemon** 的总超时上限；单 slot 5min 由 judge 层另行控制。
    """
    log_path = log_path or Path.home() / ".claude/logs/usage-eval/daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    daemon_timeout_sec = _resolve_daemon_timeout(daemon_timeout_sec)

    pid1 = os.fork()
    if pid1 > 0:
        os.waitpid(pid1, 0)  # 收割中间子进程
        return 0
    # === in first child ===
    os.setsid()

    pid2 = os.fork()
    if pid2 > 0:
        os._exit(0)
    # === in grandchild (real daemon) ===
    try:
        os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

        with open(log_path, "ab", buffering=0) as f:
            os.dup2(f.fileno(), 1)
            os.dup2(f.fileno(), 2)
        try:
            os.close(0)
        except OSError:
            pass

        wd_pid = os.fork()
        if wd_pid == 0:
            import time as _t
            _t.sleep(daemon_timeout_sec)
            try:
                os.kill(os.getppid(), 9)
            except Exception:
                pass
            os._exit(0)

        try:
            payload()
        finally:
            try:
                os.kill(wd_pid, 9)
            except Exception:
                pass
    except Exception:
        traceback.print_exc()
        os._exit(2)
    os._exit(0)
