"""Stage 2.7 — --concurrency N tests for `eval all` / `eval <skill>`.

We don't spawn real claude; we monkeypatch eval_run to a sleep-then-
return stub and assert (a) concurrency=N actually runs work in
parallel (total wall < N * single duration), (b) results are reported
in submission order regardless of completion order, (c) one scenario
failing does not break the others.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from one_context.cli import _run_many, build_parser
import argparse


class _FakeOutcome:
    def __init__(self, overall: str, run_id: str = "rid"):
        self.overall = overall
        self.run_id = run_id


def _stub_run_factory(*, per_scenario_ms: int = 50, fail_set=None):
    """Build a fake `runner.run` that sleeps and returns based on target name."""
    fail_set = fail_set or set()
    log: list[tuple[str, float]] = []

    def fake_run(*, repo_root, target, keep_tmp, skill_override, with_diff):
        t0 = time.perf_counter()
        time.sleep(per_scenario_ms / 1000)
        log.append((target, time.perf_counter() - t0))
        if target in fail_set:
            return _FakeOutcome("FAIL", run_id=f"fail-{target}")
        return _FakeOutcome("PASS", run_id=f"pass-{target}")

    return fake_run, log


def _ns(**overrides) -> argparse.Namespace:
    """Quick argparse.Namespace builder."""
    base = dict(concurrency=1, keep_tmp=False, diff=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_concurrency_1_runs_sequential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    stub, log = _stub_run_factory(per_scenario_ms=40)
    monkeypatch.setattr("one_context.eval.runner.run", stub)

    rows = [("sk", f"scn{i}") for i in range(4)]
    t0 = time.perf_counter()
    rc = _run_many(tmp_path, rows, _ns(concurrency=1))
    elapsed = time.perf_counter() - t0

    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    # 4 PASS lines, in submission order
    assert len(out) == 4
    for i, line in enumerate(out):
        assert line.startswith("PASS")
        assert f"sk/scn{i}" in line
    # 4 × 40ms = 160ms minimum; allow generous overhead
    assert elapsed >= 0.16
    assert elapsed < 0.4  # serial; must NOT have parallelism speedup


def test_concurrency_4_runs_in_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    stub, log = _stub_run_factory(per_scenario_ms=80)
    monkeypatch.setattr("one_context.eval.runner.run", stub)

    rows = [("sk", f"scn{i}") for i in range(4)]
    t0 = time.perf_counter()
    rc = _run_many(tmp_path, rows, _ns(concurrency=4))
    elapsed = time.perf_counter() - t0

    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 4
    # Output order must be submission order even though completion order varies
    for i, line in enumerate(out):
        assert f"sk/scn{i}" in line
    # 4 in parallel of 80ms each ≈ 80ms-ish. Serial would be 320ms.
    # Be generous; we just need to prove "not serial":
    assert elapsed < 0.25, f"expected <250ms in parallel, got {elapsed*1000:.0f}ms"


def test_one_failure_does_not_abort_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    stub, _ = _stub_run_factory(per_scenario_ms=10, fail_set={"sk/scn1"})
    monkeypatch.setattr("one_context.eval.runner.run", stub)

    rows = [("sk", f"scn{i}") for i in range(3)]
    rc = _run_many(tmp_path, rows, _ns(concurrency=3))

    assert rc == 1  # any FAIL → non-zero
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 3
    assert out[0].startswith("PASS")
    assert out[1].startswith("FAIL")
    assert out[2].startswith("PASS")


def test_concurrency_zero_falls_back_to_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """`--concurrency 0` or negative → treat as 1 (no division-by-zero)."""
    stub, _ = _stub_run_factory(per_scenario_ms=5)
    monkeypatch.setattr("one_context.eval.runner.run", stub)
    rows = [("sk", "scn0"), ("sk", "scn1")]
    assert _run_many(tmp_path, rows, _ns(concurrency=0)) == 0
    assert _run_many(tmp_path, rows, _ns(concurrency=-1)) == 0


def test_cli_parses_concurrency_flag() -> None:
    args = build_parser().parse_args([
        "eval", "all", "--concurrency", "4",
    ])
    assert args.concurrency == 4


def test_exceptions_surface_as_err_and_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """Runner raising on one scenario → ERR row, other scenarios still run."""
    def fake_run(*, repo_root, target, keep_tmp, skill_override, with_diff):
        if target == "sk/boom":
            raise RuntimeError("nope")
        return _FakeOutcome("PASS")
    monkeypatch.setattr("one_context.eval.runner.run", fake_run)

    rows = [("sk", "ok1"), ("sk", "boom"), ("sk", "ok2")]
    rc = _run_many(tmp_path, rows, _ns(concurrency=2))

    assert rc == 1
    cap = capsys.readouterr()
    out_lines = cap.out.splitlines()
    err_lines = cap.err.splitlines()
    assert any("PASS\tsk/ok1" in ln for ln in out_lines)
    assert any("PASS\tsk/ok2" in ln for ln in out_lines)
    assert any("ERR \tsk/boom\tnope" in ln for ln in err_lines)
