"""Stage 2.1 — CLI dispatch tests for `onecxt eval ... snapshot`.

These tests exercise the argparse wiring (positional token
juggling) + the dispatch branch in ``_cmd_eval_dispatch``. The
underlying ``baseline.snapshot()`` logic has its own unit tests
in test_baseline.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.cli import build_parser, _cmd_eval_dispatch


def _make_repo_with_run(
    tmp_path: Path,
    *,
    skill: str = "demo",
    scenario: str = "scn",
    run_id: str = "1000000000-aaaaaa",
    overall: str = "PASS",
    skill_override: dict | None = None,
) -> Path:
    """Build a fake repo root with ``skills/<skill>/evals/<scenario>/__reports/<runId>/``."""
    root = tmp_path / "repo"
    scn_dir = root / "skills" / skill / "evals" / scenario
    run_dir = scn_dir / "__reports" / run_id
    run_dir.mkdir(parents=True)
    run = {
        "run_schema_version": "1",
        "skill": skill,
        "scenario": scenario,
        "run_id": run_id,
        "overall": overall,
        "target_path_sha256": "abc123",
    }
    if skill_override is not None:
        run["skill_override"] = skill_override
    (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
    (run_dir / "report.html").write_text("<html/>", encoding="utf-8")
    return root


def _parse(*argv: str):
    return build_parser().parse_args(list(argv))


def test_cli_snapshot_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_repo_with_run(tmp_path)
    args = _parse(
        "--root", str(root),
        "eval", "demo/scn", "snapshot",
        "--reason", "initial baseline",
    )
    rc = _cmd_eval_dispatch(root, args)
    assert rc == 0

    bdir = root / "skills" / "demo" / "evals" / "scn" / "__baselines"
    baseline = json.loads((bdir / "baseline.json").read_text(encoding="utf-8"))
    assert baseline["snapshot_reason"] == "initial baseline"
    assert baseline["snapshot_run_id"] == "1000000000-aaaaaa"
    assert baseline["target_path_sha256_at_snapshot"] == "abc123"

    out = capsys.readouterr().out
    assert "snapshot OK" in out
    assert "demo/scn" in out


def test_cli_snapshot_missing_reason(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_repo_with_run(tmp_path)
    args = _parse(
        "--root", str(root),
        "eval", "demo/scn", "snapshot",
    )
    rc = _cmd_eval_dispatch(root, args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "snapshot requires --reason" in err
    # nothing was written
    assert not (root / "skills" / "demo" / "evals" / "scn" / "__baselines").exists()


def test_cli_snapshot_refuses_fail_run(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_repo_with_run(tmp_path, overall="FAIL")
    args = _parse(
        "--root", str(root),
        "eval", "demo/scn", "snapshot",
        "--reason", "x",
    )
    rc = _cmd_eval_dispatch(root, args)
    assert rc == 2
    assert "refuse to snapshot" in capsys.readouterr().err


def test_cli_snapshot_refuses_override_run(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _make_repo_with_run(
        tmp_path, skill_override={"dir": "/tmp/x", "files": ["SKILL.md"]},
    )
    args = _parse(
        "--root", str(root),
        "eval", "demo/scn", "snapshot",
        "--reason", "x",
    )
    rc = _cmd_eval_dispatch(root, args)
    assert rc == 2
    assert "--skill-override run" in capsys.readouterr().err


def test_cli_snapshot_missing_scenario_dir(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = tmp_path / "empty-repo"
    root.mkdir()
    args = _parse(
        "--root", str(root),
        "eval", "nope/missing", "snapshot",
        "--reason", "x",
    )
    rc = _cmd_eval_dispatch(root, args)
    assert rc == 2
    assert "scenario dir missing" in capsys.readouterr().err


def test_cli_snapshot_pin_run_id(tmp_path: Path) -> None:
    root = _make_repo_with_run(tmp_path, run_id="1000000000-aaaaaa")
    # add a second, newer run that we will NOT pick
    run2 = root / "skills" / "demo" / "evals" / "scn" / "__reports" / "2000000000-bbbbbb"
    run2.mkdir(parents=True)
    (run2 / "run.json").write_text(json.dumps({
        "run_schema_version": "1",
        "skill": "demo", "scenario": "scn",
        "run_id": "2000000000-bbbbbb",
        "overall": "PASS",
        "target_path_sha256": "xyz999",
    }), encoding="utf-8")

    args = _parse(
        "--root", str(root),
        "eval", "demo/scn", "snapshot",
        "--reason", "pin older",
        "--run-id", "1000000000-aaaaaa",
    )
    rc = _cmd_eval_dispatch(root, args)
    assert rc == 0
    baseline = json.loads(
        (root / "skills/demo/evals/scn/__baselines/baseline.json").read_text(
            encoding="utf-8"))
    assert baseline["snapshot_run_id"] == "1000000000-aaaaaa"
    assert baseline["target_path_sha256_at_snapshot"] == "abc123"
