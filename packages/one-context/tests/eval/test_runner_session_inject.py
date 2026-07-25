"""runner.py — session inject hook + cleanup (Stage 2.7.C.1).

Tests the two helpers in isolation (`_maybe_inject_session`,
`_cleanup_session_file`) rather than spawning a full _single_run, which
would tangle with in-progress runner refactors. Source-grep guards lock
the hook is wired into _single_run at the right spot.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from one_context.eval import runner as R
from one_context.eval import session_inject as si_mod
from one_context.eval.scenario_config import (
    ScenarioConfig,
    SessionInjectConfig,
    load_scenario,
)


def _make_scenario(
    tmp_path: Path,
    *,
    enabled: bool = True,
    schema_version: str | None = None,
    mock_rounds: list[tuple[str, str, str]] | None = None,
) -> tuple[Path, ScenarioConfig]:
    """Build a scenario dir with optional mock_rounds/ and return (dir, cfg).

    `mock_rounds` is a list of (round_id, tool_name, tool_result) tuples.
    """
    scn = tmp_path / "scn"
    scn.mkdir()
    body = (
        "query: 'do thing for {{ target_path }}'\n"
        "target_path: features/_evals/foo/\n"
    )
    if enabled:
        body += "session_inject:\n  enabled: true\n  mock_rounds_dir: mock_rounds/\n"
        if schema_version:
            body += f"  schema_version: '{schema_version}'\n"

    (scn / "scenario.yaml").write_text(body, encoding="utf-8")

    if enabled and mock_rounds is not None:
        mock_dir = scn / "mock_rounds"
        mock_dir.mkdir()
        for i, (rid, tool, result) in enumerate(mock_rounds, start=1):
            (mock_dir / f"round-{i:02d}-{rid}.yaml").write_text(
                f"round_id: {rid}\n"
                f"tool_name: {tool}\n"
                f"tool_result: '{result}'\n",
                encoding="utf-8",
            )

    cfg = load_scenario(scn)
    return scn, cfg


# ── _maybe_inject_session ──────────────────────────────────────────────────


def test_maybe_inject_none_when_session_inject_omitted(tmp_path: Path) -> None:
    """No session_inject block → helper returns None (default v1 path)."""
    scn, cfg = _make_scenario(tmp_path, enabled=False)
    out = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=tmp_path / "sbx",
        run_id="r1", rendered_query="q", requested_model_hint="m",
    )
    assert out is None


def test_maybe_inject_none_when_enabled_false(tmp_path: Path) -> None:
    """Explicit `session_inject: { enabled: false }` → helper returns None."""
    scn = tmp_path / "scn"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: features/_evals/foo/\n"
        "session_inject:\n  enabled: false\n",
        encoding="utf-8",
    )
    cfg = load_scenario(scn)
    out = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=tmp_path / "sbx",
        run_id="r1", rendered_query="q", requested_model_hint=None,
    )
    assert out is None


def test_maybe_inject_returns_meta_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """enabled=true → injector runs and returns full meta dict."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    scn, cfg = _make_scenario(
        tmp_path,
        enabled=True,
        schema_version="2.1.156",
        mock_rounds=[
            ("hn", "WebFetch", "hn-payload"),
            ("blog", "WebFetch", "blog-payload"),
        ],
    )
    meta = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
        run_id="rid-123", rendered_query="my query",
        requested_model_hint="claude-opus-4-7",
    )
    assert meta is not None
    assert meta["round_count"] == 2
    assert meta["round_ids"] == ["hn", "blog"]
    assert meta["cc_cli_version"] == "2.1.156"
    assert meta["session_schema_version"] == "2.1.156"
    assert meta["schema_version_mismatch"] is False
    assert "injected_session_id" in meta
    # Forged file: 1 user + 2*(tool_use+tool_result) + 1 R-5 治理 C
    # closing assistant message = 6 messages.
    forged = Path(meta["forged_jsonl_path"])
    assert forged.is_file()
    lines = [l for l in forged.read_text().splitlines() if l.strip()]
    assert len(lines) == 6


def test_maybe_inject_flags_schema_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """scenario pins 2.1.155 but live cc says 2.1.156 → mismatch=True + warn."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    scn, cfg = _make_scenario(
        tmp_path,
        enabled=True,
        schema_version="2.1.155",  # different from "live" 2.1.156
        mock_rounds=[("r1", "Bash", "ok")],
    )
    with caplog.at_level("WARNING", logger="one_context.eval.runner"):
        meta = R._maybe_inject_session(
            scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
            run_id="rid-mm", rendered_query="q",
            requested_model_hint="claude-opus-4-7",
        )
    assert meta is not None
    assert meta["schema_version_mismatch"] is True
    # The warn message mentions both versions for grep-ability.
    assert any("2.1.155" in r.message and "2.1.156" in r.message
               for r in caplog.records)


def test_maybe_inject_model_hint_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """requested_model_hint=None (scenario defers) → injector gets a default model."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    scn, cfg = _make_scenario(
        tmp_path, enabled=True,
        mock_rounds=[("r1", "Bash", "ok")],
    )
    meta = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
        run_id="rid-defer", rendered_query="q",
        requested_model_hint=None,  # defer to runner-resolved
    )
    assert meta is not None
    # The injected assistant message carries the fallback model.
    forged = Path(meta["forged_jsonl_path"])
    msgs = [json.loads(l) for l in forged.read_text().splitlines() if l.strip()]
    asst = next(m for m in msgs if m["type"] == "assistant")
    assert asst["message"]["model"] == "claude-opus-4-7"  # the helper's default


# ── R-5 治理 C: prefill terminator (closing assistant + end_turn) ──────


def test_prefill_terminator_uses_baseline_artifact_when_present(
    tmp_path: Path,
) -> None:
    """Reads baseline/artifacts/<target_path> as the closing message body."""
    scn = tmp_path / "scn"
    art = scn / "baseline" / "artifacts" / "production" / "info-radar" / "04-report.md"
    art.parent.mkdir(parents=True)
    art.write_text("# 04 report\nfinal content here", encoding="utf-8")
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: production/info-radar/04-report.md\n",
        encoding="utf-8",
    )
    cfg = R.load_scenario(scn)

    term = R._build_prefill_terminator(scenario_dir=scn, scen_cfg=cfg)
    assert term is not None
    assert "任务已完成" in term
    assert "production/info-radar/04-report.md" in term
    assert "final content here" in term


def test_prefill_terminator_falls_back_to_final_text_md(
    tmp_path: Path,
) -> None:
    """No artifact at target_path → fall back to baseline/final_text.md."""
    scn = tmp_path / "scn"
    (scn / "baseline").mkdir(parents=True)
    (scn / "baseline" / "final_text.md").write_text(
        "cc said: all done", encoding="utf-8",
    )
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: missing.md\n", encoding="utf-8",
    )
    cfg = R.load_scenario(scn)

    term = R._build_prefill_terminator(scenario_dir=scn, scen_cfg=cfg)
    assert term is not None
    assert "cc said: all done" in term


def test_prefill_terminator_stop_sentinel_when_no_baseline(
    tmp_path: Path,
) -> None:
    """No baseline files → minimal stop sentinel (still ends with end_turn)."""
    scn = tmp_path / "scn"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: foo/bar.md\n", encoding="utf-8",
    )
    cfg = R.load_scenario(scn)

    term = R._build_prefill_terminator(scenario_dir=scn, scen_cfg=cfg)
    assert term is not None
    assert "任务已完成" in term
    assert "foo/bar.md" in term


def test_forged_session_contains_closing_assistant_when_terminator_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E: forged jsonl last line is assistant+end_turn (R-5 C signal)."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    # Hand-roll scenario with a concrete target_path file + matching baseline.
    scn = tmp_path / "scn-c1"
    scn.mkdir()
    (scn / "scenario.yaml").write_text(
        "query: 'do thing'\n"
        "target_path: features/_evals/foo/result.md\n"
        "session_inject:\n  enabled: true\n  mock_rounds_dir: mock_rounds/\n",
        encoding="utf-8",
    )
    (scn / "mock_rounds").mkdir()
    (scn / "mock_rounds" / "round-01-r1.yaml").write_text(
        "round_id: r1\ntool_name: Bash\ntool_result: ok\n",
        encoding="utf-8",
    )
    art = scn / "baseline" / "artifacts" / "features" / "_evals" / "foo" / "result.md"
    art.parent.mkdir(parents=True)
    art.write_text("baseline final body", encoding="utf-8")

    from one_context.eval.scenario_config import load_scenario
    cfg = load_scenario(scn)

    meta = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
        run_id="rid-c1", rendered_query="q",
        requested_model_hint="claude-opus-4-7",
    )
    assert meta is not None

    forged = Path(meta["forged_jsonl_path"])
    last = json.loads(
        [l for l in forged.read_text().splitlines() if l.strip()][-1]
    )
    assert last["type"] == "assistant"
    assert last["message"]["stop_reason"] == "end_turn"
    txt = last["message"]["content"][0]["text"]
    assert "任务已完成" in txt
    assert "baseline final body" in txt


# ── R-5 治理 B: disallow 扩面 ──────────────────────────────────────────────


def test_disallow_auto_adds_cc_builtin_external_tools_when_not_in_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When mock_rounds only contains Bash, WebSearch/WebFetch are still banned.

    Treats R-5 root cause: cc escapes to WebSearch/WebFetch when its
    mocked-tool is denied; both must be in disallow to actually block escape.
    """
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    scn, cfg = _make_scenario(
        tmp_path, enabled=True,
        mock_rounds=[("b1", "Bash", "stdout")],
    )
    meta = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
        run_id="rid-b1", rendered_query="q",
        requested_model_hint="claude-opus-4-7",
    )
    assert meta is not None
    # Bash first (from mock), then the two builtins
    assert meta["disallowed_tools"] == ["Bash", "WebSearch", "WebFetch"]


def test_disallow_skips_builtin_already_in_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If mock_rounds already contains WebFetch, only WebSearch is added on top.

    Order and uniqueness: mock-first, then builtins in CC_BUILTIN_EXTERNAL
    declaration order, no duplicates.
    """
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    scn, cfg = _make_scenario(
        tmp_path, enabled=True,
        mock_rounds=[("w1", "WebFetch", "wf"), ("b1", "Bash", "stdout")],
    )
    meta = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
        run_id="rid-b2", rendered_query="q",
        requested_model_hint="claude-opus-4-7",
    )
    assert meta is not None
    # WebFetch + Bash from mock; only WebSearch added (no duplicate WebFetch)
    assert meta["disallowed_tools"] == ["WebFetch", "Bash", "WebSearch"]


def test_disallow_mcp_tools_kept_plus_builtins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mcp__* tools from mock are preserved + WebSearch/WebFetch appended."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    si_mod.detect_cc_version.cache_clear()
    monkeypatch.setattr(si_mod, "detect_cc_version", lambda: "2.1.156")

    scn, cfg = _make_scenario(
        tmp_path, enabled=True,
        mock_rounds=[
            ("m1", "mcp__codefusesearchmcp__webFetch", "mcp"),
            ("b1", "Bash", "stdout"),
        ],
    )
    meta = R._maybe_inject_session(
        scen_cfg=cfg, scenario_dir=scn, sandbox_root=sbx,
        run_id="rid-b3", rendered_query="q",
        requested_model_hint="claude-opus-4-7",
    )
    assert meta is not None
    assert meta["disallowed_tools"] == [
        "mcp__codefusesearchmcp__webFetch", "Bash", "WebSearch", "WebFetch",
    ]


# ── _cleanup_session_file ──────────────────────────────────────────────────


def test_cleanup_removes_forged_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)

    # Create the forged file manually (avoid coupling to injector internals).
    target = si_mod.session_file_path(sbx, "rid-cleanup")
    target.parent.mkdir(parents=True)
    target.write_text("dummy\n", encoding="utf-8")
    assert target.exists()

    R._cleanup_session_file(sbx, "rid-cleanup")
    assert not target.exists()


def test_cleanup_is_noop_when_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No file → no exception (e.g. session_inject was disabled this run)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    # Must not raise:
    R._cleanup_session_file(tmp_path / "sbx", "rid-none")


def test_cleanup_prunes_empty_project_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After removing the only file, the project-hash dir is pruned too,
    so the user's ~/.claude/projects/ listing doesn't accrete dead entries."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)

    target = si_mod.session_file_path(sbx, "rid-prune")
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    proj_dir = target.parent

    R._cleanup_session_file(sbx, "rid-prune")
    assert not target.exists()
    assert not proj_dir.exists(), "empty project-hash dir should be removed"


def test_cleanup_keeps_dir_when_other_files_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the project-hash dir still has sibling sessions, do NOT prune it."""
    sbx = tmp_path / "sbx"
    sbx.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)

    target = si_mod.session_file_path(sbx, "rid-keep")
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    (target.parent / "some-other-session.jsonl").write_text("y", encoding="utf-8")

    R._cleanup_session_file(sbx, "rid-keep")
    assert not target.exists()
    assert target.parent.exists()


# ── source-grep guards for the _single_run integration site ───────────────


def test_runner_source_calls_maybe_inject() -> None:
    """Lock the hook insertion point: _single_run must call _maybe_inject_session
    AFTER rendered_query is computed AND pass resume_session_id to provider.

    Source-grep is intentionally brittle — refactors are fine but must
    update this test, surfacing the contract change.
    """
    src = Path(R.__file__).read_text(encoding="utf-8")
    # The call site exists.
    assert "_maybe_inject_session(" in src
    # The result is consumed (we use the session id, not the meta blindly).
    assert "resume_session_id = (" in src
    # run.json carries the session_inject section.
    assert 'run["session_inject"] = session_inject_meta' in src
    # cleanup is wired into the finally block.
    assert "_cleanup_session_file(sandbox.path, injected_session_id)" in src


def test_runner_source_passes_resume_to_provider() -> None:
    """provider.run_provider call MUST include resume_session_id=resume_session_id
    — otherwise the forged session is created but the spawn doesn't use it."""
    src = Path(R.__file__).read_text(encoding="utf-8")
    # Find the run_provider call and verify resume_session_id is in it.
    start = src.find("prov = provider_mod.run_provider(")
    assert start != -1, "run_provider call site moved"
    end = src.find(")", start)
    call_block = src[start:end]
    assert "resume_session_id=resume_session_id" in call_block
