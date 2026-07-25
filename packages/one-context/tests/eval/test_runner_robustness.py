"""Provider-failure robustness tests for the eval runner (ISS-019 / Stage 1.1.8).

For each of 5 provider failure modes, the runner must:
- still write `__reports/<runId>/run.json` with the right `provider_status`
  and `overall == "FAIL"` (overall_pass requires `prov.ok`, so a failed
  provider can never PASS regardless of judge verdict)
- still write `__reports/<runId>/report.html` containing a red banner /
  `provider_status` marker so the user has a debug entry point
- still tear down the sandbox

R-5 治理 D (design §16.7.5): the judge no longer skips when the provider
fails — it now runs with a `provider_status_notice` so the LLM can score
partial progress against `tool_calls + baseline artifacts`. We assert the
notice was attached and `overall == FAIL`; we do NOT assert the judge was
skipped.

Failure modes covered:
  1. api_error      — provider returns aggregated JSON with is_error=true
  2. timeout        — subprocess.run raises TimeoutExpired
  3. interrupted    — provider raises KeyboardInterrupt (runner catches)
  4. empty_stdout   — provider stdout is empty
  5. other          — provider stdout is non-JSON garbage

We patch ``provider.subprocess`` (the module attribute on `prov_mod`) so
that only the provider's subprocess calls are intercepted; git / sandbox
calls keep using the real subprocess.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from one_context.eval import judge as J
from one_context.eval import provider as prov_mod
from one_context.eval import runner as R


def _init_repo(tmp_path: Path) -> Path:
    """Build a minimal git repo with a skill+scenario that triggers the runner."""
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
        "judge_model: m\n"
        "artifacts:\n"
        "  - production/out.md\n"
        "default_rubric: |\n"
        "  must produce production/out.md with non-empty body\n",
        encoding="utf-8",
    )

    scn = skill / "evals" / "case"
    scn.mkdir(parents=True)
    # ISS-020 / 022 (Phase 2.0): scenario uses `target_path` + main-repo fixture
    # under `features/_evals/`; no scenario-private fixture subtree, no `fixture:` block.
    (scn / "scenario.yaml").write_text(
        "query: q\n"
        "target_path: features/_evals/foo/\n"
        "provider:\n"
        "  model: m\n"
        "  timeoutMs: 1000\n"
        "threshold: 0.5\n",
        encoding="utf-8",
    )
    # Materialize the eval-fixture feature in the main repo (ISS-022 shared pool).
    feat = root / "features" / "_evals" / "foo" / "production"
    feat.mkdir(parents=True)
    (feat / "out.md").write_text("hello world body", encoding="utf-8")
    (feat.parent / "spec.md").write_text("---\n---\n\nspec body", encoding="utf-8")

    prov_dir = root / "evals" / "providers"
    prov_dir.mkdir(parents=True)
    (prov_dir / "claude-code.js").write_text("// mocked\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), check=True)
    return root


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _init_repo(tmp_path)
    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    # R-5 治理 D: judge runs even on provider failure (with a notice).
    # Stub the spawn so we don't fork a real `claude` process.
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": false, "score": 0.1, "reason": "stub"}',
    )
    return root


def _patch_provider_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    fake_run,
) -> None:
    """Replace prov_mod's ``subprocess`` attribute with a wrapper that only
    intercepts ``run`` — other attributes (TimeoutExpired, etc) fall through.

    This isolates the mock to calls inside ``prov_mod`` so git / sandbox
    subprocess calls keep working.
    """
    fake = SimpleNamespace(
        run=fake_run,
        TimeoutExpired=subprocess.TimeoutExpired,
        CompletedProcess=subprocess.CompletedProcess,
        PIPE=subprocess.PIPE,
        DEVNULL=subprocess.DEVNULL,
    )
    monkeypatch.setattr(prov_mod, "subprocess", fake)


def _read_run_json(outcome: R.RunOutcome) -> dict[str, Any]:
    return json.loads(outcome.run_json_path.read_text(encoding="utf-8"))


def _assert_failure_artifacts(outcome: R.RunOutcome, expected_status: str) -> None:
    """Common asserts: run.json + report.html exist, overall FAIL, judge ran with notice.

    R-5 治理 D: judge no longer skips on provider failure; it runs with a
    `provider_status_notice` so partial progress is still scored. overall
    is still FAIL because `overall_pass` requires `prov.ok`.
    """
    assert outcome.overall == "FAIL"
    assert outcome.run_json_path.is_file(), "run.json must be written even when provider fails"
    assert outcome.report_html_path.is_file(), "report.html must be written even when provider fails"

    run = _read_run_json(outcome)
    assert run["overall"] == "FAIL"
    assert run["provider_status"] == expected_status, (
        f"provider_status mismatch: got {run['provider_status']!r}, "
        f"want {expected_status!r}"
    )
    judge = run["judge"]
    # R-5 D: judge ran (has model + pass/score) AND carries the notice.
    assert "skipped" not in judge, (
        "R-5 治理 D: judge must run on provider failure, not skip"
    )
    assert judge.get("provider_status_notice"), (
        "judge.provider_status_notice must explain the partial-progress scoring"
    )
    # cost_usd field always present
    assert "cost_usd" in run
    assert isinstance(run["cost_usd"], (int, float))

    html = outcome.report_html_path.read_text(encoding="utf-8")
    # C4: red banner is a flagged Tailwind block — check for the literal class
    # name AND the rose accent so a future re-skin still triggers this when
    # someone removes the banner.
    assert "banner-red" in html, "report.html must include red banner block"
    assert "Provider failed" in html or "PROVIDER FAILED" in html.upper(), (
        "red banner must surface 'Provider failed' headline"
    )
    assert expected_status in html, (
        f"report.html must surface provider_status text {expected_status!r}"
    )


# ---------------------------------------------------------------------------
# 1. api_error
# ---------------------------------------------------------------------------

def test_runner_handles_api_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider returns aggregated JSON with is_error=true → provider_status=api_error."""

    def fake_run(cmd, **kwargs):  # noqa: ARG001
        agg = {
            "ok": False,
            "is_error": True,
            "exit_code": 1,
            "duration_ms": 800,
            "requested_model": "m",
            "actual_model": "m-20250901",
            "final_text": "API Error: rate limit exceeded",
            "tool_calls": [],
            "stream_path": "",
            "timeout": False,
            "stderr_tail": "rate-limit\n",
        }
        return subprocess.CompletedProcess(
            args=cmd, returncode=1,
            stdout=json.dumps(agg) + "\n",
            stderr="rate-limit",
        )

    _patch_provider_subprocess(monkeypatch, fake_run)
    outcome = R.run(repo_root=repo, target="demo/case")
    _assert_failure_artifacts(outcome, "api_error")


# ---------------------------------------------------------------------------
# 2. timeout
# ---------------------------------------------------------------------------

def test_runner_handles_timeout(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess.run raises TimeoutExpired → provider_status=timeout."""

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 1))

    _patch_provider_subprocess(monkeypatch, fake_run)
    outcome = R.run(repo_root=repo, target="demo/case")
    _assert_failure_artifacts(outcome, "timeout")

    run = _read_run_json(outcome)
    assert run["timeout"] is True


# ---------------------------------------------------------------------------
# 3. interrupted (KeyboardInterrupt — caught at runner layer)
# ---------------------------------------------------------------------------

def test_runner_handles_keyboard_interrupt(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provider raises KeyboardInterrupt → runner catches → provider_status=interrupted."""

    def fake_run(cmd, **kwargs):  # noqa: ARG001
        raise KeyboardInterrupt()

    _patch_provider_subprocess(monkeypatch, fake_run)
    outcome = R.run(repo_root=repo, target="demo/case")
    _assert_failure_artifacts(outcome, "interrupted")

    run = _read_run_json(outcome)
    assert "KeyboardInterrupt" in run["stderr_tail"]


# ---------------------------------------------------------------------------
# 4. empty_stdout
# ---------------------------------------------------------------------------

def test_runner_handles_empty_stdout(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provider stdout is empty → provider_status=empty_stdout."""

    def fake_run(cmd, **kwargs):  # noqa: ARG001
        return subprocess.CompletedProcess(
            args=cmd, returncode=2,
            stdout="",
            stderr="node: missing module\n",
        )

    _patch_provider_subprocess(monkeypatch, fake_run)
    outcome = R.run(repo_root=repo, target="demo/case")
    _assert_failure_artifacts(outcome, "empty_stdout")


# ---------------------------------------------------------------------------
# 5. other (e.g. unparseable JSON / unexpected exception)
# ---------------------------------------------------------------------------

def test_runner_handles_other_unparseable_json(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provider stdout is non-JSON garbage → provider_status=other."""

    def fake_run(cmd, **kwargs):  # noqa: ARG001
        return subprocess.CompletedProcess(
            args=cmd, returncode=0,
            stdout="this is not json at all\n",
            stderr="",
        )

    _patch_provider_subprocess(monkeypatch, fake_run)
    outcome = R.run(repo_root=repo, target="demo/case")
    _assert_failure_artifacts(outcome, "other")


# ---------------------------------------------------------------------------
# extract_cost_usd helper
# ---------------------------------------------------------------------------

def test_extract_cost_usd_from_stream_path(tmp_path: Path) -> None:
    """extract_cost_usd reads the last 'result' line's total_cost_usd."""
    sp = tmp_path / "stream.jsonl"
    sp.write_text(
        '{"type":"system","subtype":"init"}\n'
        '{"type":"assistant","message":{"content":[]}}\n'
        '{"type":"result","is_error":false,"total_cost_usd":0.0123}\n',
        encoding="utf-8",
    )
    assert prov_mod.extract_cost_usd(sp) == pytest.approx(0.0123)


def test_extract_cost_usd_missing_file_returns_zero(tmp_path: Path) -> None:
    assert prov_mod.extract_cost_usd(tmp_path / "does-not-exist.jsonl") == 0.0


def test_extract_cost_usd_no_result_line_returns_zero(tmp_path: Path) -> None:
    sp = tmp_path / "stream.jsonl"
    sp.write_text(
        '{"type":"system"}\n{"type":"assistant","message":{"content":[]}}\n',
        encoding="utf-8",
    )
    assert prov_mod.extract_cost_usd(sp) == 0.0
