"""finalize_session tests (Phase 2.8 M3).

Covers `finalize.py` against the contracts inherited from M2 hook_writer
(`event_type` / `cc_session_id` / `_failure` jsonl-only fields, failed
rounds carrying cc-native error tool_result) plus the new M3 surface:

- happy path: 3 rounds → 3 yaml + baseline + LLM mock invoked
- cc_session_id filter: most-frequent picked when session.cc_session_id
  is missing, with a warning
- cc_session_id filter: session.cc_session_id wins over jsonl noise
- failed round: yaml has cc-native `{error, is_error}` tool_result and
  boundary_type rewritten from `failed_tool` → `local_tool`/`mcp_call`
- jsonl-only field drop: every yaml round_trips through MockRound
- empty workspace: baseline/artifacts is created but empty (no crash)
- LLM call failure: degrades to placeholder + llm_error.txt persisted +
  status stays `finalizing` so user can retry
- LLM prompt: every F-NN id from the info-radar negative-case library
  appears in the rendered prompt (no silent drops)
- wrong status: SessionWrongState when not in `recording`
- mock_rounds_digest: dict[str, sha256_hex_str] with 8-byte hex prefix
  no longer enough — must be full sha256 length
- final_text.md: present when transcript readable, empty + warning
  otherwise
- candidate-list markdown shape: D1/F1 headings detectable for the M4
  parser
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from one_context.eval.session_inject import MockRound
from one_context.recorder import finalize as finalize_mod
from one_context.recorder import llm_client
from one_context.recorder.finalize import finalize_session
from one_context.recorder.session import (
    SessionWrongState,
    abort_session,
    load_session,
    start_session,
)


# ── helpers ─────────────────────────────────────────────────────────────


def _round(
    *,
    seq: int,
    tool_name: str = "Bash",
    tool_input: dict | None = None,
    tool_result: Any = "ok\n",
    cc_session_id: str = "cc-target",
    boundary: str = "local_tool",
    event_type: str = "PostToolUse",
    failure: dict | None = None,
) -> dict:
    inp = tool_input or {"command": f"echo {seq}"}
    record = {
        "round_id": f"round-{seq:02d}-{tool_name.lower()}-{seq:08x}",
        "tool_name": tool_name,
        "tool_input": inp,
        "tool_result": tool_result,
        "assistant_thinking": "",
        "boundary_type": boundary,
        "event_type": event_type,
        "cc_session_id": cc_session_id,
    }
    if failure is not None:
        record["_failure"] = failure
    return record


def _write_jsonl(session_dir: Path, records: list[dict]) -> None:
    p = session_dir / "rounds.jsonl"
    with p.open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _stub_llm(
    monkeypatch: pytest.MonkeyPatch, text: str | None = None
) -> dict:
    """Replace `llm_client.call_llm_for_draft` with a capturing stub."""
    captured: dict[str, Any] = {}

    def fake(prompt: str, *, model: str | None = None,
             timeout_sec: int = 0) -> str:
        captured["prompt"] = prompt
        captured["model"] = model
        return text if text is not None else (
            "# Judge Prompt Draft — stub\n\n"
            "## 这次录制为什么算成功\n\nstub\n\n"
            "## 候选 query\n\nstub query\n\n"
            "## 判定维度（LLM 给 0-1 分）\n\n"
            "### D1: stub-d1\n**判定标准**：stub\n**权重**：0.5\n\n"
            "### D2: stub-d2\n**判定标准**：stub\n**权重**：0.5\n\n"
            "## 虚假通过反例（出现任一即 FAIL）\n\n"
            "### F1: stub-f1\n**特征**：stub\n\n"
            "### F2: stub-f2\n**特征**：stub\n\n"
            "## 未覆盖反例\n\n（全覆盖）\n\n"
            "## 总分阈值\n\n`pass_threshold: 0.7`\n"
        )

    monkeypatch.setattr(llm_client, "call_llm_for_draft", fake)
    monkeypatch.setattr(finalize_mod.llm_client, "call_llm_for_draft", fake)
    return captured


# ── happy path ──────────────────────────────────────────────────────────


def test_finalize_happy_path_writes_staging(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn",
        cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1, tool_name="Bash", tool_input={"command": "ls"},
               tool_result={"stdout": "a\nb\n", "stderr": "",
                            "interrupted": False}),
        _round(seq=2, tool_name="WebFetch",
               tool_input={"url": "https://x", "prompt": "extract"},
               tool_result="some markdown body"),
        _round(seq=3, tool_name="mcp__plug__nav",
               tool_input={"url": "about:blank"},
               tool_result=[{"ok": True}],
               boundary="mcp_call"),
    ])
    # Drop a workspace artifact so baseline snapshot has something.
    (sdir / "workspace" / "production").mkdir(parents=True)
    (sdir / "workspace" / "production" / "out.md").write_text(
        "hello world", encoding="utf-8"
    )

    captured = _stub_llm(monkeypatch)
    try:
        draft = finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    assert "stub-d1" in draft  # LLM stub was invoked & returned
    assert captured.get("prompt"), "LLM was not called"

    staging = sdir / "staging"
    yamls = sorted((staging / "mock_rounds").glob("*.yaml"))
    assert len(yamls) == 3
    # baseline snapshot copied the workspace artifact
    assert (staging / "baseline" / "artifacts" /
            "production" / "out.md").read_text() == "hello world"
    # final_text and meta written
    assert (staging / "baseline" / "final_text.md").exists()
    meta = json.loads((staging / "baseline" / "meta.json").read_text())
    assert set(meta.keys()) >= {
        "recorded_at", "cc_cli_version", "model",
        "working_tree_sha", "target_path_sha256", "mock_rounds_digest",
    }
    assert meta["target_path_sha256"] is None  # M4 fills it
    # draft markdown persisted to staging/
    assert (staging / "judge_candidates_draft.md").read_text() == draft


# ── cc_session_id filter ────────────────────────────────────────────────


def test_finalize_filters_by_session_cc_session_id(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1, cc_session_id="cc-target"),
        _round(seq=2, cc_session_id="cc-noise"),  # parent cc Bash leak
        _round(seq=3, cc_session_id="cc-target"),
    ])

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    yamls = sorted((sdir / "staging" / "mock_rounds").glob("*.yaml"))
    assert len(yamls) == 2  # noise round excluded


def test_finalize_picks_most_frequent_when_session_id_missing(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id=None,
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1, cc_session_id="cc-A"),
        _round(seq=2, cc_session_id="cc-A"),
        _round(seq=3, cc_session_id="cc-A"),
        _round(seq=4, cc_session_id="cc-B"),
    ])

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    yamls = sorted((sdir / "staging" / "mock_rounds").glob("*.yaml"))
    assert len(yamls) == 3
    warnings = (sdir / "staging" / "warnings.txt").read_text()
    assert "cc-A" in warnings and "2 distinct" in warnings


# ── failed-round handling ───────────────────────────────────────────────


def test_finalize_failed_round_yaml_has_cc_native_error_shape(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(
            seq=1,
            tool_name="WebFetch",
            tool_input={"url": "https://blocked"},
            tool_result={"error": "proxy denied", "is_error": True},
            boundary="failed_tool",
            event_type="PostToolUseFailure",
            failure={"error": "proxy denied", "is_interrupt": False},
        ),
    ])

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    yamls = list((sdir / "staging" / "mock_rounds").glob("*.yaml"))
    assert len(yamls) == 1
    obj = yaml.safe_load(yamls[0].read_text(encoding="utf-8"))
    # boundary_type rewritten failed_tool → local_tool (WebFetch is native)
    assert obj["boundary_type"] == "local_tool"
    # tool_result kept as cc-native error envelope
    assert obj["tool_result"] == {"error": "proxy denied", "is_error": True}
    # MockRound roundtrips cleanly (no extra="forbid" violation)
    MockRound.model_validate(obj)


def test_finalize_failed_mcp_round_keeps_mcp_call_boundary(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(
            seq=1,
            tool_name="mcp__plug__do",
            tool_result={"error": "denied", "is_error": True},
            boundary="failed_tool",
            event_type="PostToolUseFailure",
            failure={"error": "denied", "is_interrupt": False},
        ),
    ])
    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    yamls = list((sdir / "staging" / "mock_rounds").glob("*.yaml"))
    obj = yaml.safe_load(yamls[0].read_text())
    assert obj["boundary_type"] == "mcp_call"
    MockRound.model_validate(obj)


# ── jsonl-only field drop ──────────────────────────────────────────────


def test_finalize_drops_jsonl_only_fields_from_yaml(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1),
        _round(seq=2, tool_name="WebFetch",
               tool_input={"url": "https://x"}, tool_result="body"),
    ])
    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    for yp in sorted((sdir / "staging" / "mock_rounds").glob("*.yaml")):
        obj = yaml.safe_load(yp.read_text(encoding="utf-8"))
        forbidden = {"event_type", "cc_session_id", "_failure"}
        assert forbidden.isdisjoint(obj.keys()), (
            f"{yp.name} leaked jsonl-only fields: {set(obj.keys()) & forbidden}"
        )
        # Belt + suspenders: round-trips through MockRound (extra=forbid).
        MockRound.model_validate(obj)


# ── empty workspace ─────────────────────────────────────────────────────


def test_finalize_with_empty_workspace_still_succeeds(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])
    # workspace/ exists but is empty (created by start_session)

    _stub_llm(monkeypatch)
    try:
        draft = finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    arts = sdir / "staging" / "baseline" / "artifacts"
    assert arts.is_dir()
    assert list(arts.iterdir()) == []
    assert draft  # non-empty markdown


# ── M9: workspace_mirror_from ──────────────────────────────────────────


def test_finalize_workspace_mirror_from_copies_external_dir(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """mirror_from path is cp'd into workspace before snapshot."""
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])

    # External artifact dir (simulates child cc writing to project tree)
    external = tmp_path / "project_production"
    (external / "info-radar").mkdir(parents=True)
    (external / "info-radar" / "04-report.md").write_text(
        "real report", encoding="utf-8"
    )

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id, workspace_mirror_from=external)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    arts = sdir / "staging" / "baseline" / "artifacts"
    assert (arts / "info-radar" / "04-report.md").read_text() == "real report"


def test_finalize_workspace_mirror_overlay_keeps_existing_files(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Mirror overlays: existing workspace files survive when not in mirror src."""
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])
    # Pre-existing workspace file (e.g. from session.cwd convention)
    (sdir / "workspace" / "pre.txt").write_text("preexisting", encoding="utf-8")

    external = tmp_path / "ext"
    external.mkdir()
    (external / "new.txt").write_text("from-mirror", encoding="utf-8")

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id, workspace_mirror_from=external)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    arts = sdir / "staging" / "baseline" / "artifacts"
    assert (arts / "pre.txt").read_text() == "preexisting"
    assert (arts / "new.txt").read_text() == "from-mirror"


def test_finalize_workspace_mirror_missing_dir_writes_warning(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Non-existent mirror_from path warns but doesn't raise."""
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])

    bogus = tmp_path / "does-not-exist"

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id, workspace_mirror_from=bogus)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    warnings_txt = sdir / "staging" / "warnings.txt"
    assert warnings_txt.exists()
    assert "workspace_mirror_from not found" in warnings_txt.read_text()


def test_finalize_workspace_mirror_file_path_writes_warning(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """mirror_from pointing at a file (not dir) warns but doesn't raise."""
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])

    a_file = tmp_path / "lonely.txt"
    a_file.write_text("not a dir", encoding="utf-8")

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id, workspace_mirror_from=a_file)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    warnings_txt = sdir / "staging" / "warnings.txt"
    assert warnings_txt.exists()
    assert "not a directory" in warnings_txt.read_text()


def test_finalize_without_mirror_param_still_works(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No mirror_from kw → backward-compatible no-op (M3 behaviour)."""
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])
    (sdir / "workspace" / "in-session.txt").write_text("x", encoding="utf-8")

    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    arts = sdir / "staging" / "baseline" / "artifacts"
    assert (arts / "in-session.txt").read_text() == "x"


# ── LLM failure degradation ────────────────────────────────────────────


def test_finalize_llm_failure_degrades_to_placeholder(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])

    def boom(prompt: str, *, model: str | None = None,
             timeout_sec: int = 0) -> str:
        raise llm_client.LLMCallError("model not available")

    monkeypatch.setattr(llm_client, "call_llm_for_draft", boom)
    monkeypatch.setattr(finalize_mod.llm_client, "call_llm_for_draft", boom)

    draft = finalize_session(sess.session_id)
    try:
        assert "LLM 调用失败" in draft  # degraded placeholder
        err = (sdir / "staging" / "llm_error.txt").read_text(encoding="utf-8")
        assert "model not available" in err
        # mock_rounds still written; baseline still snapped
        assert list((sdir / "staging" / "mock_rounds").glob("*.yaml"))
        # NOTE on state: design §6.3 LLMDraftFailure → session stays in
        # `finalizing` so the user can retry finalize OR move straight into
        # commit_finalize with a hand-edited draft. We do NOT roll back
        # to `recording` (would lose the staged mock_rounds work). Check
        # BEFORE abort_session (which flips status to `aborted`).
        sess2 = load_session(sess.session_id)
        assert sess2.status == "finalizing"
    finally:
        abort_session(sess.session_id, keep_staging=False)


# ── LLM prompt content ─────────────────────────────────────────────────


def test_finalize_prompt_inlines_every_negative_case_id(
    recorder_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Skill-owned library lives at skills/<skill>/evals/_negative_cases.md.
    # We stage a synthetic 5-entry library so the test verifies the loader
    # → renderer pipeline without depending on the real info-radar library
    # (which can grow / shrink over time).
    repo = recorder_tmp.parent / "repo"
    (repo / "skills" / "info-radar" / "evals").mkdir(parents=True)
    (repo / "skills" / "info-radar" / "SKILL.md").write_text(
        "# info-radar", encoding="utf-8"
    )
    fake_lib = "\n".join(
        f"## F-{i:02d}: synthetic negative case {i}\n\n**特征**: t{i}\n"
        for i in range(1, 6)
    )
    (repo / "skills" / "info-radar" / "evals" / "_negative_cases.md").write_text(
        fake_lib, encoding="utf-8"
    )
    # Point resolve_repo_root() at the staged repo for this test.
    monkeypatch.setenv("ONECXT_RECORDER_REPO_ROOT", str(repo))

    sess = start_session(
        "info-radar", "scn", cc_session_id="cc-target",
        repo_root=repo,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1, tool_name="WebFetch",
               tool_input={"url": "https://hn"},
               tool_result=[{"title": "x"}]),
    ])

    captured = _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    prompt = captured["prompt"]
    for i in range(1, 6):
        token = f"F-{i:02d}"
        assert token in prompt, f"prompt missing {token}: not injected"
    # also: skill / scenario name reach the prompt
    assert "info-radar" in prompt
    assert "scn" in prompt


def test_finalize_prompt_falls_back_to_default_when_skill_has_no_library(
    recorder_tmp: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Skill exists but ships no evals/_negative_cases.md → loader falls
    # back to framework's negative_cases/_default.md.
    repo = recorder_tmp.parent / "repo_default"
    (repo / "skills" / "no-lib-skill").mkdir(parents=True)
    (repo / "skills" / "no-lib-skill" / "SKILL.md").write_text(
        "# no-lib-skill", encoding="utf-8"
    )
    monkeypatch.setenv("ONECXT_RECORDER_REPO_ROOT", str(repo))

    sess = start_session(
        "no-lib-skill", "scn", cc_session_id="cc-target",
        repo_root=repo,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1, tool_name="WebFetch",
               tool_input={"url": "https://x"},
               tool_result=[{"title": "y"}]),
    ])

    captured = _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    prompt = captured["prompt"]
    # _default.md contains the "通用虚假通过反例库（fallback）" header.
    assert "通用" in prompt and "fallback" in prompt


def test_finalize_loader_walks_up_when_cwd_is_subdir(
    recorder_tmp: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # Regression: previously load_negative_case_library used Path.cwd() /
    # 'skills/<skill>/...' verbatim. When the MCP server was launched from
    # a sub-directory of the repo (e.g. packages/one-context), this missed
    # the skill-owned library and silently fell back to _default.md. The
    # loader now walks up to the first ancestor containing
    # `skills/<skill>/SKILL.md`, so cwd may be any descendant of the repo.
    repo = tmp_path / "fake_repo"
    sub = repo / "packages" / "one-context"
    sub.mkdir(parents=True)
    (repo / "skills" / "info-radar" / "evals").mkdir(parents=True)
    (repo / "skills" / "info-radar" / "SKILL.md").write_text(
        "# info-radar", encoding="utf-8"
    )
    fake_lib = "\n".join(
        f"## F-{i:02d}: walk-up case {i}\n" for i in range(1, 4)
    )
    (repo / "skills" / "info-radar" / "evals" / "_negative_cases.md").write_text(
        fake_lib, encoding="utf-8"
    )

    # Point both the cwd-style env AND the explicit sub-dir at the package
    # subdirectory — this is the exact shape of the bug we hit in the
    # 2026-06-02 finalize run.
    monkeypatch.setenv("ONECXT_RECORDER_REPO_ROOT", str(sub))
    monkeypatch.chdir(sub)

    sess = start_session(
        "info-radar", "scn", cc_session_id="cc-target",
        repo_root=repo,  # session resolves SKILL.md via this; loader uses env/cwd
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1, tool_name="WebFetch",
               tool_input={"url": "https://x"},
               tool_result=[{"title": "y"}]),
    ])

    captured = _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    prompt = captured["prompt"]
    # Skill-owned library reached the prompt — fallback header MUST NOT.
    for i in range(1, 4):
        assert f"F-{i:02d}" in prompt, (
            f"prompt missing F-{i:02d}: loader didn't walk up to the repo root"
        )
    assert "fallback" not in prompt, (
        "prompt unexpectedly contains _default.md content — loader silently "
        "fell back when skill-owned library was reachable via walk-up"
    )


# ── wrong-state guard ──────────────────────────────────────────────────


def test_finalize_rejects_non_recording_status(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    s = load_session(sess.session_id)
    s.status = "aborted"
    from one_context.recorder.session import save_session

    save_session(s)
    try:
        with pytest.raises(SessionWrongState):
            finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=False)


# ── mock_rounds_digest shape ───────────────────────────────────────────


def test_mock_rounds_digest_is_full_sha256_per_round(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [
        _round(seq=1),
        _round(seq=2, tool_name="WebFetch",
               tool_input={"url": "https://x"}, tool_result="x"),
    ])
    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    meta = json.loads(
        (sdir / "staging" / "baseline" / "meta.json").read_text()
    )
    digest = meta["mock_rounds_digest"]
    assert isinstance(digest, dict)
    assert len(digest) == 2
    for rid, h in digest.items():
        assert isinstance(rid, str) and rid
        assert isinstance(h, str)
        assert re.fullmatch(r"[0-9a-f]{64}", h), f"not a sha256 hex: {h!r}"


# ── final_text.md best-effort ──────────────────────────────────────────


def test_final_text_empty_with_warning_when_transcript_missing(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-no-such-transcript-xyz123",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])
    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    txt = (sdir / "staging" / "baseline" / "final_text.md").read_text()
    assert txt == ""
    warnings = (sdir / "staging" / "warnings.txt").read_text()
    assert "transcript" in warnings


def test_final_text_extracted_from_transcript_when_present(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Fake out ~/.claude/projects/<hash>/<cc_session>.jsonl
    fake_home = tmp_path / "home"
    projects = fake_home / ".claude" / "projects" / "fake-hash"
    projects.mkdir(parents=True)
    cc_sid = "cc-with-transcript-abc"
    transcript = projects / f"{cc_sid}.jsonl"
    # Two user turns + one assistant text turn (the recorder picks the LAST
    # assistant text).
    lines = [
        json.dumps({"type": "user", "message": {"role": "user",
                                                "content": "首问 hello"}}),
        json.dumps({"type": "assistant",
                    "message": {"role": "assistant",
                                "content": [
                                    {"type": "text", "text": "interim"},
                                ]}}),
        json.dumps({"type": "assistant",
                    "message": {"role": "assistant",
                                "content": [
                                    {"type": "text",
                                     "text": "最终输出 done"},
                                ]}}),
    ]
    transcript.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))

    sess = start_session(
        "demo", "scn", cc_session_id=cc_sid,
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1, cc_session_id=cc_sid)])
    captured = _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    txt = (sdir / "staging" / "baseline" / "final_text.md").read_text()
    assert "最终输出 done" in txt
    # And the query_draft path lifted the first user msg into the prompt.
    assert "首问 hello" in captured["prompt"]


def test_meta_model_lifted_from_cc_transcript_not_env(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """meta.model must read cc transcript's assistant.model, not env.

    Regression for the bug that wrote ANTHROPIC_MODEL ("GLM-5.1") into
    meta.model when the recorder LLM ran on GLM but cc itself ran claude.
    """
    fake_home = tmp_path / "home"
    projects = fake_home / ".claude" / "projects" / "fake-hash"
    projects.mkdir(parents=True)
    cc_sid = "cc-with-model-info"
    transcript = projects / f"{cc_sid}.jsonl"
    lines = [
        json.dumps({"type": "user", "message": {"role": "user",
                                                "content": "x"}}),
        json.dumps({"type": "assistant",
                    "message": {"role": "assistant",
                                "model": "claude-opus-4-7",
                                "content": [{"type": "text", "text": "ok"}]}}),
    ]
    transcript.write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))
    # Poison the env so the regression would write GLM-5.1 if we still
    # fell through to it.
    monkeypatch.setenv("ANTHROPIC_MODEL", "GLM-5.1")

    sess = start_session(
        "demo", "scn", cc_session_id=cc_sid,
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1, cc_session_id=cc_sid)])
    _stub_llm(monkeypatch)
    try:
        finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    meta = json.loads((sdir / "staging" / "baseline" / "meta.json").read_text())
    assert meta["model"] == "claude-opus-4-7"
    assert meta["model"] != "GLM-5.1"


def test_meta_working_tree_sha_uses_repo_root_not_session_dir(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """working_tree_sha must hash `git status` from repo_root, not session_dir.

    Regression for the bug that always returned 'unknown' because session_dir
    (/tmp/onecxt-recorder/...) is never a git repo.
    """
    import subprocess
    # Make repo_with_skill an actual git repo so git status returns 0.
    subprocess.run(["git", "init", "-q"], cwd=repo_with_skill, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"],
                   cwd=repo_with_skill, check=True)
    subprocess.run(["git", "config", "user.name", "t"],
                   cwd=repo_with_skill, check=True)

    sess = start_session(
        "demo", "scn", cc_session_id="cc-x",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])
    _stub_llm(monkeypatch)
    try:
        # Pass repo_root explicitly — the mcp_server normally does this from
        # ONECXT_RECORDER_REPO_ROOT env.
        finalize_session(sess.session_id, repo_root=repo_with_skill)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    meta = json.loads((sdir / "staging" / "baseline" / "meta.json").read_text())
    assert meta["working_tree_sha"] != "unknown", (
        "git status sha should resolve when repo_root is a real git repo; "
        "regression: still hashing session_dir which is not a git repo"
    )
    # It's a sha256, even when working tree is clean (hash of empty string is
    # still e3b0c44... — that's *expected* for a clean tree; the regression
    # we're guarding against is literal string 'unknown').
    assert len(meta["working_tree_sha"]) == 64


# ── candidate-list markdown shape ──────────────────────────────────────


def test_candidate_list_markdown_has_d_and_f_sections(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    _write_jsonl(sdir, [_round(seq=1)])
    _stub_llm(monkeypatch)
    try:
        draft = finalize_session(sess.session_id)
    finally:
        abort_session(sess.session_id, keep_staging=True)

    # M4's commit_finalize parser will key off these headings.
    assert re.search(r"^### D1:", draft, re.MULTILINE), \
        "candidate list missing `### D1:` heading"
    assert re.search(r"^### F1:", draft, re.MULTILINE), \
        "candidate list missing `### F1:` heading"
    assert "pass_threshold" in draft
