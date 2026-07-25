"""End-to-end runner tests for the Phase 2.6.B assertions layer.

Reuses the same mock-provider + replayed-judge pattern as
`test_runner_e2e.py` but builds scenarios with `assertions:` declared
in `eval.yaml` / `scenario.yaml`. The assertions run before the LLM
judge; blocking failures short-circuit the judge entirely.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from one_context.eval import provider as prov_mod
from one_context.eval import judge as J
from one_context.eval import runner as R


def _init_repo_with_assertions(
    tmp_path: Path,
    *,
    skill_assertions_yaml: str,
    scenario_extra_yaml: str = "",
) -> Path:
    """Build a repo whose skill/eval.yaml carries declarative assertions."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=str(root), check=True)

    skill = root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo", encoding="utf-8")
    (skill / "eval.yaml").write_text(
        "artifacts:\n"
        "  - production/out.md\n"
        "  - production/data.json\n"
        "default_rubric: |\n"
        "  produce a report with a sensible body\n"
        + skill_assertions_yaml,
        encoding="utf-8",
    )

    scn = skill / "evals" / "case"
    scn.mkdir(parents=True)
    (scn / "scenario.yaml").write_text(
        "query: |\n"
        "  please write under {{ target_path }}\n"
        "target_path: features/foo/\n"
        "provider:\n"
        "  model: m\n"
        "  timeoutMs: 1000\n"
        "threshold: 0.5\n"
        + scenario_extra_yaml,
        encoding="utf-8",
    )

    feat = root / "features" / "foo" / "production"
    feat.mkdir(parents=True)
    (feat / "_seed").write_text("placeholder", encoding="utf-8")

    prov_dir = root / "evals" / "providers"
    prov_dir.mkdir(parents=True)
    (prov_dir / "claude-code.js").write_text("// mocked\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), check=True)
    return root


def _setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    write_files: dict[str, str],
    judge_pass: bool = True,
):
    """Boilerplate: redirect sandbox tmp + mock provider that drops the given
    files under target_path + replay judge with `judge_pass`."""
    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    def fake_run(**kwargs):
        cwd = Path(kwargs["cwd"])
        for rel, content in write_files.items():
            full = cwd / "features" / "foo" / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"],
            final_text="produced files",
            tool_calls=[],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)

    payload = (
        '{"pass": true, "score": 0.9, "reason": "ok"}'
        if judge_pass
        else '{"pass": false, "score": 0.2, "reason": "no"}'
    )
    monkeypatch.setattr(J, "_spawn_judge", lambda prompt, model: payload)


def test_assertions_all_pass_judge_runs_overall_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All assertions pass + judge passes → overall PASS, judge spawned."""
    skill_yaml = (
        "assertions:\n"
        "  - id: out-md-exists\n"
        "    kind: file_exists\n"
        "    path: production/out.md\n"
        "  - id: data-json-valid\n"
        "    kind: json_valid\n"
        "    path: production/data.json\n"
    )
    root = _init_repo_with_assertions(tmp_path, skill_assertions_yaml=skill_yaml)

    judge_called: dict = {"n": 0}

    def fake_judge(prompt, model):
        judge_called["n"] += 1
        return '{"pass": true, "score": 0.9, "reason": "ok"}'

    monkeypatch.setattr(J, "_spawn_judge", fake_judge)

    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    def fake_run(**kwargs):
        cwd = Path(kwargs["cwd"])
        (cwd / "features" / "foo" / "production" / "out.md").write_text(
            "hello body", encoding="utf-8")
        (cwd / "features" / "foo" / "production" / "data.json").write_text(
            '{"x": 1}', encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"], actual_model=kwargs["model"],
            final_text="done", tool_calls=[],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"
    assert judge_called["n"] == 1, "judge should run when assertions pass"

    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    assert run["assertions_summary"]["all_blocking_passed"] is True
    assert run["assertions_summary"]["passed"] == 2
    statuses = {a["id"]: a["status"] for a in run["assertions"]}
    assert statuses == {"out-md-exists": "pass", "data-json-valid": "pass"}
    assert "skipped" not in run["judge"]
    assert run["judge"]["pass"] is True


def test_blocking_assertion_fail_skips_judge_overall_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blocking assertion fails → judge skipped, overall FAIL, no judge spawn."""
    skill_yaml = (
        "assertions:\n"
        "  - id: required-out\n"
        "    kind: file_exists\n"
        "    path: production/out.md\n"
        "  - id: data-json\n"
        "    kind: json_valid\n"
        "    path: production/data.json\n"
    )
    root = _init_repo_with_assertions(tmp_path, skill_assertions_yaml=skill_yaml)

    judge_called: dict = {"n": 0}
    monkeypatch.setattr(J, "_spawn_judge",
                        lambda p, m: (judge_called.update(n=judge_called["n"]+1)
                                      or '{"pass": true, "score": 0.9, "reason": "ok"}'))

    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    def fake_run(**kwargs):
        cwd = Path(kwargs["cwd"])
        # Deliberately DO NOT create out.md — that's the blocking miss.
        (cwd / "features" / "foo" / "production" / "data.json").write_text(
            '{"x": 1}', encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"], actual_model=kwargs["model"],
            final_text="forgot out.md", tool_calls=[],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "FAIL"
    assert judge_called["n"] == 0, "judge MUST NOT run when blocking assertion fails"

    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    assert run["judge"] == {
        "skipped": "blocking_assertion_failed",
        "failed_ids": ["required-out"],
    }
    assert run["assertions_summary"]["blocking_failed"] == 1
    assert run["assertions_summary"]["passed"] == 1


def test_non_blocking_assertion_fail_judge_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """blocking=false fails → judge still runs; overall decided by judge."""
    skill_yaml = (
        "assertions:\n"
        "  - id: nice-to-have\n"
        "    kind: file_exists\n"
        "    path: production/optional.md\n"
        "    blocking: false\n"
    )
    root = _init_repo_with_assertions(tmp_path, skill_assertions_yaml=skill_yaml)
    _setup(tmp_path, monkeypatch,
           write_files={"production/out.md": "body"},
           judge_pass=True)

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"

    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    assert run["assertions_summary"]["blocking_failed"] == 0
    # the non-blocking assertion did fail
    assert any(a["id"] == "nice-to-have" and a["status"] == "fail"
               for a in run["assertions"])
    # judge still ran
    assert "skipped" not in run["judge"]
    assert run["judge"]["pass"] is True


def test_assertion_error_treated_as_blocking_when_blocking_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handler raising (e.g. JSON parse on a non-JSON file) → status=error
    + counted toward blocking_failed when blocking=True."""
    skill_yaml = (
        "assertions:\n"
        "  - id: broken-json\n"
        "    kind: json_valid\n"
        "    path: production/data.json\n"
    )
    root = _init_repo_with_assertions(tmp_path, skill_assertions_yaml=skill_yaml)
    _setup(tmp_path, monkeypatch,
           write_files={"production/data.json": "not { json"},
           judge_pass=True)

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "FAIL"

    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    [a] = run["assertions"]
    assert a["status"] == "error"
    assert a["detail"]["error_class"] in {"JSONDecodeError", "ValueError"}
    assert run["assertions_summary"]["blocking_failed"] == 1
    assert run["judge"]["skipped"] == "blocking_assertion_failed"


def test_scenario_assertions_skip_disables_skill_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`assertions_skip:` removes a skill default by id so the scenario
    isn't blocked by it. Verifies the merge contract end-to-end."""
    skill_yaml = (
        "assertions:\n"
        "  - id: default-out\n"
        "    kind: file_exists\n"
        "    path: production/out.md\n"
    )
    scenario_extra = (
        "assertions_skip:\n"
        "  - default-out\n"
    )
    root = _init_repo_with_assertions(
        tmp_path,
        skill_assertions_yaml=skill_yaml,
        scenario_extra_yaml=scenario_extra,
    )
    # provider does NOT create out.md but the assertion is skipped, so
    # nothing is blocking.
    _setup(tmp_path, monkeypatch, write_files={}, judge_pass=True)

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"

    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    assert run["assertions"] == []
    assert run["assertions_summary"]["total"] == 0
    assert "skipped" not in run["judge"]


def test_scenario_assertion_id_collision_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If scenario redeclares an `id` without `assertions_skip`, runner
    surfaces a config error (caller can choose how to handle)."""
    skill_yaml = (
        "assertions:\n"
        "  - id: dup\n"
        "    kind: file_exists\n"
        "    path: production/out.md\n"
    )
    scenario_extra = (
        "assertions:\n"
        "  - id: dup\n"
        "    kind: file_exists\n"
        "    path: production/other.md\n"
    )
    root = _init_repo_with_assertions(
        tmp_path,
        skill_assertions_yaml=skill_yaml,
        scenario_extra_yaml=scenario_extra,
    )
    _setup(tmp_path, monkeypatch, write_files={}, judge_pass=True)

    with pytest.raises(ValueError, match="collides"):
        R.run(repo_root=root, target="demo/case")
