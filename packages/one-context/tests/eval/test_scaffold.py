"""Stage 2.4 — scaffold.init_scenario() + CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from one_context.cli import build_parser, _cmd_eval_dispatch
from one_context.eval.scaffold import (
    InitError,
    init_scenario,
)


def _mk_skill(root: Path, skill: str, *, with_eval_yaml: bool = False) -> Path:
    sk = root / "skills" / skill
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("# stub", encoding="utf-8")
    if with_eval_yaml:
        (sk / "eval.yaml").write_text(
            "artifacts: ['production/**']\n"
            "default_rubric: 'be correct'\n"
            "judge_model: claude-opus-4-7\n",
            encoding="utf-8",
        )
    return sk


def test_init_creates_three_files(tmp_path: Path) -> None:
    _mk_skill(tmp_path, "foo", with_eval_yaml=True)
    out = init_scenario(repo_root=tmp_path, skill="foo", scenario="bar")

    assert out.scenario_dir == tmp_path / "skills/foo/evals/bar"
    assert len(out.files_created) == 3
    assert (out.scenario_dir / "scenario.yaml").is_file()
    assert (out.scenario_dir / "ground_truth" / "pass-01.yaml").is_file()
    assert (out.scenario_dir / "ground_truth" / "fail-01.yaml").is_file()
    assert out.warnings == []


def test_init_warns_when_skill_eval_yaml_missing(tmp_path: Path) -> None:
    _mk_skill(tmp_path, "foo", with_eval_yaml=False)
    out = init_scenario(repo_root=tmp_path, skill="foo", scenario="bar")
    assert any("eval.yaml missing" in w for w in out.warnings)


def test_init_template_contains_target_path_and_rubric(tmp_path: Path) -> None:
    _mk_skill(tmp_path, "foo")
    out = init_scenario(repo_root=tmp_path, skill="foo", scenario="bar")
    body = (out.scenario_dir / "scenario.yaml").read_text(encoding="utf-8")
    # template is parameterized on (skill, scenario) — the literal slash form
    # appears in the header comment so re-runs are diff-friendly
    assert "foo/bar" in body
    assert "target_path:" in body
    assert "rubric:" in body
    assert "{{ target_path }}" in body


def test_init_refuses_when_skill_missing(tmp_path: Path) -> None:
    with pytest.raises(InitError, match="skill dir missing"):
        init_scenario(repo_root=tmp_path, skill="missing", scenario="bar")


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    _mk_skill(tmp_path, "foo")
    init_scenario(repo_root=tmp_path, skill="foo", scenario="bar")
    with pytest.raises(InitError, match="already exists"):
        init_scenario(repo_root=tmp_path, skill="foo", scenario="bar")


# ──────────────────────── CLI dispatch ────────────────────────

def _parse(*argv: str):
    return build_parser().parse_args(list(argv))


def test_cli_init_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _mk_skill(tmp_path, "foo", with_eval_yaml=True)
    args = _parse("--root", str(tmp_path), "eval", "init", "foo/bar")
    rc = _cmd_eval_dispatch(tmp_path, args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "init OK" in out
    assert "scenario.yaml" in out
    assert "ground_truth/pass-01.yaml" in out


def test_cli_init_missing_target(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    args = _parse("--root", str(tmp_path), "eval", "init")
    rc = _cmd_eval_dispatch(tmp_path, args)
    assert rc == 2
    assert "init` requires" in capsys.readouterr().err


def test_cli_init_refuse_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _mk_skill(tmp_path, "foo", with_eval_yaml=True)
    args = _parse("--root", str(tmp_path), "eval", "init", "foo/bar")
    assert _cmd_eval_dispatch(tmp_path, args) == 0
    capsys.readouterr()
    # second invocation must fail
    args2 = _parse("--root", str(tmp_path), "eval", "init", "foo/bar")
    rc = _cmd_eval_dispatch(tmp_path, args2)
    assert rc == 2
    assert "already exists" in capsys.readouterr().err


def test_cli_all_alias_maps_to_all(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """`eval --all` with no scenarios produces the same '(no scenarios)' line as `eval all`."""
    args = _parse("--root", str(tmp_path), "eval", "all")
    rc = _cmd_eval_dispatch(tmp_path, args)
    assert rc == 0
    assert "(no scenarios)" in capsys.readouterr().out


def test_cli_skill_no_match(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """`eval <skill>` when the skill has zero scenarios."""
    _mk_skill(tmp_path, "foo", with_eval_yaml=True)
    args = _parse("--root", str(tmp_path), "eval", "foo")
    rc = _cmd_eval_dispatch(tmp_path, args)
    assert rc == 2
    assert "no scenarios under skill" in capsys.readouterr().err
