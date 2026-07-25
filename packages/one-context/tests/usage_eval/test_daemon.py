"""daemon double-fork 测试。

注意：测试在 pytest 进程里真做 fork——子进程必须用 ``os._exit`` 退出，
否则会触发 pytest 的 atexit/finalizer，污染父进程状态。
"""
import os
import time

from one_context.usage_eval.daemon import (
    DAEMON_TIMEOUT_ENV,
    DEFAULT_DAEMON_TIMEOUT_SEC,
    _resolve_daemon_timeout,
    double_fork_and_run,
)


def test_double_fork_runs_payload_in_background(tmp_path):
    """父立即返回 0，孙子被 init/launchd 收养（ppid != 父）"""
    flag = tmp_path / "ran.flag"
    parent_pid = os.getpid()

    def payload():
        flag.write_text(str(os.getppid()))

    rc = double_fork_and_run(payload, log_path=tmp_path / "daemon.log")
    assert rc == 0  # 父立即返回

    # 等子进程 < 2s 完成
    for _ in range(40):
        if flag.exists():
            break
        time.sleep(0.05)
    assert flag.exists(), "孙子进程没在 2s 内写文件"

    # 孙子被 init/launchd 收养 → ppid ≠ 父
    written_ppid = int(flag.read_text())
    assert written_ppid != parent_pid


def test_double_fork_returns_immediately(tmp_path):
    """父进程返回时间 < 500ms（即使 payload 慢）"""
    flag = tmp_path / "slow.flag"

    def slow_payload():
        time.sleep(0.5)  # 模拟慢 payload
        flag.write_text("done")

    t0 = time.time()
    rc = double_fork_and_run(slow_payload, log_path=tmp_path / "slow.log")
    elapsed = time.time() - t0
    assert rc == 0
    assert elapsed < 0.5, f"父返回耗时 {elapsed:.3f}s 太长"


def test_resolve_daemon_timeout_default():
    """无 env → 用默认"""
    os.environ.pop(DAEMON_TIMEOUT_ENV, None)
    assert _resolve_daemon_timeout(DEFAULT_DAEMON_TIMEOUT_SEC) == DEFAULT_DAEMON_TIMEOUT_SEC


def test_resolve_daemon_timeout_env_overrides(monkeypatch):
    """env 设置 → 覆盖默认"""
    monkeypatch.setenv(DAEMON_TIMEOUT_ENV, "900")
    assert _resolve_daemon_timeout(DEFAULT_DAEMON_TIMEOUT_SEC) == 900


def test_resolve_daemon_timeout_env_invalid_falls_back(monkeypatch):
    """env 是垃圾值 → 回退默认"""
    monkeypatch.setenv(DAEMON_TIMEOUT_ENV, "not-a-number")
    assert _resolve_daemon_timeout(DEFAULT_DAEMON_TIMEOUT_SEC) == DEFAULT_DAEMON_TIMEOUT_SEC


def test_resolve_daemon_timeout_min_floor(monkeypatch):
    """env 设很小值 → 至少 60s（避免立即被杀）"""
    monkeypatch.setenv(DAEMON_TIMEOUT_ENV, "5")
    assert _resolve_daemon_timeout(DEFAULT_DAEMON_TIMEOUT_SEC) == 60
