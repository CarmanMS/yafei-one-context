"""Integration test for `onecxt eval judge-test` (Stage 1.1.9).

Uses the real ``skills/cover-prompt/evals/mid-video/ground_truth/`` fixture
(4 hand-curated samples: 2 pass + 2 fail), but mocks ``judge.evaluate`` so
we do NOT spawn ``claude -p`` (quota + flakiness). The test asserts:

- run_judge_test produces a row per ground-truth file
- the table contains the verdict line + matched/total
- the CLI subcommand exits 0 when matched ≥3/4, 1 otherwise

The cover-prompt assets are checked into the repo, so this test is stable.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from one_context.eval import judge as judge_mod
from one_context.eval import judge_test as jt_mod


REPO_ROOT = Path(__file__).resolve().parents[4]
COVER_PROMPT_SCENARIO = "cover-prompt/mid-video"
GT_DIR = REPO_ROOT / "skills" / "cover-prompt" / "evals" / "mid-video" / "ground_truth"


pytestmark = pytest.mark.skipif(
    not GT_DIR.is_dir(),
    reason="cover-prompt/mid-video ground_truth/ is missing",
)


def _is_fail_sample(final_text: str, artifacts: list[dict]) -> bool:
    """Heuristic: identify the fail-* samples by unique markers.

    - fail-01-wrong-paradigm uses the English phrase "Information-dense
      knowledge poster" — never appears in pass samples.
    - fail-02-no-english-prompt uses "TBD（待确认）" / "标题：TBD" — never
      appears in pass samples.
    """
    text = (final_text or "") + "\n" + "\n".join(
        (a.get("head") or "") for a in artifacts
    )
    return (
        "Information-dense knowledge poster" in text
        or "TBD（待确认）" in text
        or "TBD" in text and "标题" in text
    )


def _make_fake_judge(*, pass_for_pass: bool, pass_for_fail: bool):
    """Return a fake ``judge.evaluate`` that returns deterministic results
    keyed by sample identity (pass vs fail), letting tests force perfect
    alignment or perfect mismatch with the human label.
    """

    def fake_evaluate(*, criteria, final_text, tool_calls, artifacts, cache_dir, model):
        is_fail = _is_fail_sample(final_text or "", artifacts or [])
        if is_fail:
            # The sample's expected="fail"; "pass_for_fail" toggles whether
            # the judge agrees with the human.
            return judge_mod.JudgeResult(
                pass_=pass_for_fail,
                score=0.10 if not pass_for_fail else 0.85,
                reason="(mocked) fail sample — returning pass="
                + str(pass_for_fail),
                model="mocked",
                cached=False,
                raw="",
            )
        return judge_mod.JudgeResult(
            pass_=pass_for_pass,
            score=0.95 if pass_for_pass else 0.20,
            reason="(mocked) pass sample — returning pass="
            + str(pass_for_pass),
            model="mocked",
            cached=False,
            raw="",
        )

    return fake_evaluate


def _patch_judge(monkeypatch: pytest.MonkeyPatch, fake) -> None:
    # judge_test imports judge_mod via attribute lookup at call time
    monkeypatch.setattr(judge_mod, "evaluate", fake)
    monkeypatch.setattr(jt_mod.judge_mod, "evaluate", fake)


def test_judge_test_perfect_alignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mocked judge agrees with every ground truth → 4/4."""
    _patch_judge(
        monkeypatch,
        _make_fake_judge(pass_for_pass=True, pass_for_fail=False),
    )

    buf = io.StringIO()
    rows, matched, total = jt_mod.run_judge_test(
        repo_root=REPO_ROOT,
        target=COVER_PROMPT_SCENARIO,
        out=buf,
        color=False,
    )
    assert total == 4, "expected 4 ground-truth samples (2 pass + 2 fail)"
    assert matched == 4, f"all 4 should match, got rows={rows}"

    out = buf.getvalue()
    assert "ground_truth name" in out
    assert "expected" in out
    assert "actual judge" in out
    assert "match" in out
    assert "4/4 PASS" in out
    assert "JUDGE 可用" in out


def test_judge_test_full_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mocked judge disagrees with every ground truth → 0/4."""
    _patch_judge(
        monkeypatch,
        _make_fake_judge(pass_for_pass=False, pass_for_fail=True),
    )

    buf = io.StringIO()
    rows, matched, total = jt_mod.run_judge_test(
        repo_root=REPO_ROOT,
        target=COVER_PROMPT_SCENARIO,
        out=buf,
        color=False,
    )
    assert total == 4
    assert matched == 0
    out = buf.getvalue()
    assert "0/4 PASS" in out
    assert "JUDGE 不可用" in out


def test_judge_test_cli_exit_code_pass(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI: matched ≥3/4 → exit 0."""
    _patch_judge(
        monkeypatch,
        _make_fake_judge(pass_for_pass=True, pass_for_fail=False),
    )

    from one_context.cli import build_parser, _cmd_eval_dispatch
    parser = build_parser()
    args = parser.parse_args([
        "eval", "judge-test", COVER_PROMPT_SCENARIO,
    ])
    rc = _cmd_eval_dispatch(REPO_ROOT, args)
    assert rc == 0, f"expected exit 0 on 4/4 match, got {rc}"
    out = capsys.readouterr().out
    assert "4/4 PASS" in out


def test_judge_test_cli_exit_code_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI: matched ≤2/4 → exit 1."""
    _patch_judge(
        monkeypatch,
        _make_fake_judge(pass_for_pass=False, pass_for_fail=True),
    )

    from one_context.cli import build_parser, _cmd_eval_dispatch
    parser = build_parser()
    args = parser.parse_args([
        "eval", "judge-test", COVER_PROMPT_SCENARIO,
    ])
    rc = _cmd_eval_dispatch(REPO_ROOT, args)
    assert rc == 1, f"expected exit 1 on 0/4 match, got {rc}"


def test_judge_test_missing_sub_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI without the <skill>/<scenario> arg → exit 2 with helpful error."""
    from one_context.cli import build_parser, _cmd_eval_dispatch
    parser = build_parser()
    args = parser.parse_args(["eval", "judge-test"])
    rc = _cmd_eval_dispatch(REPO_ROOT, args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "judge-test" in err


def test_judge_test_unknown_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown skill/scenario → FileNotFoundError surfaced."""
    with pytest.raises((FileNotFoundError, ValueError)):
        jt_mod.run_judge_test(
            repo_root=REPO_ROOT,
            target="no-such-skill/no-such-scenario",
            out=io.StringIO(),
            color=False,
        )
