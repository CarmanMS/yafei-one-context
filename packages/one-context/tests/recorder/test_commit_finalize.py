"""commit_finalize tests (Phase 2.8 M4).

Covers `commit_finalize.py` against:

- happy path "全收"  → 4-file scenario dir landed, active.json cleared,
  session.status='committed', staging rmtreed
- selective keep/drop → judge_prompt.md only contains kept D/F items
- threshold override → scenario.yaml threshold updated
- invalid id (D999) → InvalidFinalizeFeedback, target dir untouched
- target_path doesn't exist → TargetPathNotFound
- ScenarioDirConflict default → raises; overwrite=True → backs up
- LLM parse failure → CommitFailure + staging preserved + status stays
- P3 double-insurance assertions: every distinct mock_rounds tool_name
  earns a `tool_call_count == 0 blocking` entry
- wrong state guard (status != finalizing) → SessionWrongState
- `!include` not used: scenario_config loads scenario.yaml directly
  (inline assertions branch)
- warnings.txt content transparently forwarded to return dict.warnings
- query / target_path missing → ambiguous → user_clarification action
- written scenario.yaml round-trips through ScenarioConfig.model_validate
- staging dir rmtreed on success
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from one_context.eval.scenario_config import load_scenario
from one_context.eval.session_inject import MockRound
from one_context.recorder import commit_finalize as commit_mod
from one_context.recorder import llm_client
from one_context.recorder.commit_finalize import (
    CommitFailure,
    InvalidFinalizeFeedback,
    ScenarioDirConflict,
    EmptyTargetPath,
    TargetPathNotFound,
    commit_finalize_session,
)
from one_context.recorder.session import (
    SessionWrongState,
    abort_session,
    get_active_session_id,
    load_session,
    start_session,
)


# ── helpers ─────────────────────────────────────────────────────────────


def _stub_feedback_llm(
    monkeypatch: pytest.MonkeyPatch, payload: dict | str,
) -> dict:
    """Replace `llm_client.call_llm_for_draft` with a stub returning JSON.

    `payload` may be the dict the LLM "would have produced" (serialized
    to JSON) OR a raw string for testing malformed-JSON paths.
    """
    captured: dict[str, Any] = {}

    def fake(prompt: str, *, model: str | None = None,
             timeout_sec: int = 0) -> str:
        captured["prompt"] = prompt
        return (
            json.dumps(payload, ensure_ascii=False)
            if isinstance(payload, dict) else payload
        )

    monkeypatch.setattr(llm_client, "call_llm_for_draft", fake)
    monkeypatch.setattr(commit_mod.llm_client, "call_llm_for_draft", fake)
    return captured


def _make_finalizing_session(
    *,
    recorder_tmp: Path,
    repo_with_skill: Path,
    skill_name: str = "demo",
    scenario_name: str = "scn",
    mock_tool_names: tuple[str, ...] = ("WebFetch", "Bash"),
    draft_md: str | None = None,
    warnings_text: str | None = None,
) -> tuple[Path, str]:
    """Spin a session through start → fabricate staging → status=finalizing.

    Bypasses the real finalize_session so we control the staging contents
    exactly. Returns (session_dir, session_id).
    """
    sess = start_session(
        skill_name, scenario_name,
        cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    sdir = Path(sess.recording_dir)
    staging = sdir / "staging"
    (staging / "mock_rounds").mkdir(parents=True)
    (staging / "baseline" / "artifacts").mkdir(parents=True)

    # Drop one mock_round per tool name so the P3 generator has variety.
    for i, tn in enumerate(mock_tool_names, start=1):
        mr = MockRound(
            round_id=f"round-{i:02d}-{tn.lower()}-{i:08x}",
            tool_name=tn,
            tool_input={"url": f"https://example/{i}"} if tn == "WebFetch"
            else {"command": f"echo {i}"},
            tool_result=f"mock-result-{i}",
            boundary_type="mcp_call" if tn.startswith("mcp__") else "local_tool",
        )
        (staging / "mock_rounds" / f"{mr.round_id}.yaml").write_text(
            yaml.safe_dump(mr.model_dump(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    # Baseline meta with target_path_sha256=None per M3 contract.
    meta = {
        "recorded_at": "2026-05-31T12:00:00+00:00",
        "cc_cli_version": "2.1.156",
        "model": "stub",
        "working_tree_sha": "deadbeef",
        "target_path_sha256": None,
        "mock_rounds_digest": {
            f"round-{i:02d}-{tn.lower()}-{i:08x}": "a" * 64
            for i, tn in enumerate(mock_tool_names, start=1)
        },
    }
    (staging / "baseline" / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (staging / "baseline" / "final_text.md").write_text(
        "final assistant output", encoding="utf-8"
    )
    (staging / "baseline" / "artifacts" / "out.txt").write_text(
        "artifact-body", encoding="utf-8"
    )

    # Candidate draft markdown.
    if draft_md is None:
        draft_md = _default_draft_md()
    (staging / "judge_candidates_draft.md").write_text(
        draft_md, encoding="utf-8"
    )

    if warnings_text:
        (staging / "warnings.txt").write_text(
            warnings_text, encoding="utf-8"
        )

    # Flip status manually so we don't depend on real finalize.
    s = load_session(sess.session_id)
    s.status = "finalizing"
    from one_context.recorder.session import save_session
    save_session(s)

    return sdir, sess.session_id


def _default_draft_md() -> str:
    return (
        "# Judge Prompt Draft — demo / scn\n\n"
        "## 这次录制为什么算成功\n\n"
        "本次录制跑通了 WebFetch + Bash 链路，产物 out.txt 生成。\n\n"
        "## 候选 query\n\n"
        "信息雷达\n\n"
        "## 判定维度（LLM 给 0-1 分）\n\n"
        "### D1: source-fidelity\n"
        "**判定标准**：baseline/artifacts/out.txt 必须存在且非空\n"
        "**权重**：0.5\n"
        "**covers**: [F-01]\n\n"
        "### D2: format-correctness\n"
        "**判定标准**：out.txt 长度 > 5 字节\n"
        "**权重**：0.5\n"
        "**covers**: [F-02]\n\n"
        "## 虚假通过反例（出现任一即 FAIL）\n\n"
        "### F1: empty-mock-fabrication\n"
        "**特征**：mock 为空时 cc 仍输出实物内容\n"
        "**反例数据来源**：baseline/artifacts/out.txt 不应出现 '幻觉'\n"
        "**covers**: [F-01]\n\n"
        "### F2: template-filler\n"
        "**特征**：出现『TBD』『待补充』模板套话\n"
        "**反例数据来源**：final_text 不应包含 'TBD'\n"
        "**covers**: [F-02]\n\n"
        "## 未覆盖反例\n\n（全覆盖）\n\n"
        "## 总分阈值\n\n`pass_threshold: 0.7`\n"
    )


def _make_target_path(repo_with_skill: Path, rel: str = "features/_evals/demo/scn/") -> str:
    abs_path = repo_with_skill / rel
    abs_path.mkdir(parents=True, exist_ok=True)
    (abs_path / "README.md").write_text("fixture", encoding="utf-8")
    return rel


# ── happy path ──────────────────────────────────────────────────────────


def test_commit_finalize_happy_path_full_accept(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(
        sid, "全收", repo_root=repo_with_skill,
    )

    scenario_dir = repo_with_skill / "skills" / "demo" / "evals" / "scn"
    # 4 deliverable files all there
    assert (scenario_dir / "scenario.yaml").is_file()
    assert (scenario_dir / "judge_prompt.md").is_file()
    assert (scenario_dir / "assertions" / "recorded.yaml").is_file()
    assert list((scenario_dir / "mock_rounds").glob("*.yaml"))
    assert (scenario_dir / "baseline" / "meta.json").is_file()

    # session is committed and active.json cleared
    s = load_session(sid)
    assert s.status == "committed"
    assert get_active_session_id() is None
    # staging dir rmtreed (session.json kept for post-commit audit)
    assert not (sdir / "staging").exists()
    assert (sdir / "session.json").is_file()

    # returned summary shape
    assert out["scenario_dir"] == str(scenario_dir)
    assert out["scenario_yaml_path"] == str(scenario_dir / "scenario.yaml")
    assert isinstance(out["files_written"], list) and out["files_written"]
    assert out["warnings"] == []
    assert out["backup_path"] is None

    # R-8 治理 (design §16.7.10): scenario.yaml must inline judge_prompt.md
    # content into the `rubric:` field so runner.judge_mod.merge_rubric
    # has something to read. Without this, evals get "no rubric configured"
    # judge fails despite a perfectly good judge_prompt.md sitting next to.
    import yaml as _y
    sy = _y.safe_load((scenario_dir / "scenario.yaml").read_text())
    judge_md_text = (scenario_dir / "judge_prompt.md").read_text()
    assert sy.get("rubric"), "scenario.yaml.rubric must be non-empty"
    assert sy["rubric"] == judge_md_text, (
        "scenario.yaml.rubric must equal the judge_prompt.md content "
        "(commit_finalize inlines the prompt verbatim)"
    )


# ── selective keep / drop ───────────────────────────────────────────────


def test_commit_finalize_selective_keep_drop(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "F1"],
        "drop_dimensions": ["D2", "F2"],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(
        sid, "保留 D1 F1，删 D2 F2", repo_root=repo_with_skill,
    )
    judge = (Path(out["scenario_dir"]) / "judge_prompt.md").read_text()
    assert "### D1:" in judge
    assert "### F1:" in judge
    assert "### D2:" not in judge
    assert "### F2:" not in judge


# ── threshold override ────────────────────────────────────────────────


def test_commit_finalize_threshold_override(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {"pass_threshold": 0.8, "D1.weight": 0.7},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(
        sid, "pass_threshold 调到 0.8，D1 权重改到 0.7",
        repo_root=repo_with_skill,
    )
    scen_path = Path(out["scenario_yaml_path"])
    raw = yaml.safe_load(scen_path.read_text(encoding="utf-8"))
    assert raw["threshold"] == 0.8
    judge = (Path(out["scenario_dir"]) / "judge_prompt.md").read_text()
    assert "pass_threshold: 0.8" in judge
    assert "**权重**：0.7" in judge


# ── invalid id ───────────────────────────────────────────────────────────


def test_commit_finalize_invalid_id_raises_and_keeps_staging(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D999"],  # D999 doesn't exist
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    with pytest.raises(InvalidFinalizeFeedback) as ei:
        commit_finalize_session(
            sid, "留 D1 D999",
            repo_root=repo_with_skill,
        )
    assert "D999" in ei.value.unknown_ids
    # scenario_dir not created
    scenario_dir = repo_with_skill / "skills" / "demo" / "evals" / "scn"
    assert not scenario_dir.exists()
    # staging still present + session still finalizing
    assert (sdir / "staging").is_dir()
    assert load_session(sid).status == "finalizing"
    abort_session(sid, keep_staging=False)


# ── target_path missing on disk ─────────────────────────────────────────


def test_commit_finalize_target_path_missing(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": "features/_evals/does/not/exist/",
        "ambiguous_intents": [],
    })

    with pytest.raises(TargetPathNotFound):
        commit_finalize_session(
            sid, "全收，target_path 用 features/_evals/does/not/exist/",
            repo_root=repo_with_skill,
        )
    abort_session(sid, keep_staging=False)


# ── ScenarioDirConflict + overwrite=True backup ──────────────────────


def test_commit_finalize_scenario_dir_conflict_raises_default(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    # Pre-create the target scenario dir + put a file inside.
    sc = repo_with_skill / "skills" / "demo" / "evals" / "scn"
    sc.mkdir(parents=True)
    (sc / "existing.txt").write_text("old", encoding="utf-8")

    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    with pytest.raises(ScenarioDirConflict):
        commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    # Existing file untouched, staging still present.
    assert (sc / "existing.txt").read_text() == "old"
    assert (sdir / "staging").is_dir()
    abort_session(sid, keep_staging=False)


def test_commit_finalize_overwrite_true_backs_up_existing(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    sc = repo_with_skill / "skills" / "demo" / "evals" / "scn"
    sc.mkdir(parents=True)
    (sc / "existing.txt").write_text("old", encoding="utf-8")

    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(
        sid, "全收", overwrite=True, repo_root=repo_with_skill,
    )
    # New scenario landed
    assert (sc / "scenario.yaml").is_file()
    # Backup created next to it
    bak = Path(out["backup_path"])
    assert bak.is_dir()
    assert (bak / "existing.txt").read_text() == "old"


# ── LLM parse failure ──────────────────────────────────────────────────


def test_commit_finalize_llm_failure_preserves_staging(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    _make_target_path(repo_with_skill)

    def boom(prompt: str, *, model: str | None = None,
             timeout_sec: int = 0) -> str:
        raise llm_client.LLMCallError("upstream rate limit")

    monkeypatch.setattr(llm_client, "call_llm_for_draft", boom)
    monkeypatch.setattr(commit_mod.llm_client, "call_llm_for_draft", boom)

    with pytest.raises(CommitFailure) as ei:
        commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    assert ei.value.reason == "llm_parse_error"
    # staging untouched, session still finalizing → user can retry
    assert (sdir / "staging").is_dir()
    assert (sdir / "staging" / "judge_candidates_draft.md").is_file()
    assert load_session(sid).status == "finalizing"
    abort_session(sid, keep_staging=False)


# ── P3 double-insurance assertions ────────────────────────────────────


def test_commit_finalize_auto_appends_p3_assertions_per_tool(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
        mock_tool_names=("WebFetch", "Bash", "mcp__plug__fetch"),
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(sid, "全收", repo_root=repo_with_skill)

    # Both the side file and the inlined scenario.assertions get them.
    ar_path = Path(out["scenario_dir"]) / "assertions" / "recorded.yaml"
    assertions = yaml.safe_load(ar_path.read_text(encoding="utf-8"))
    tool_names = {a["tool_name"] for a in assertions}
    assert tool_names == {"WebFetch", "Bash", "mcp__plug__fetch"}
    for a in assertions:
        assert a["kind"] == "tool_call_count"
        assert a["blocking"] is True
        assert a["count_min"] == 0 and a["count_max"] == 0

    # And scenario.yaml round-trips with the same set.
    scen = yaml.safe_load(
        (Path(out["scenario_dir"]) / "scenario.yaml").read_text()
    )
    inlined_tool_names = {a["tool_name"] for a in scen["assertions"]}
    assert inlined_tool_names == tool_names


# ── wrong-state guard ────────────────────────────────────────────────


def test_commit_finalize_wrong_state(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-target",
        repo_root=repo_with_skill,
    )
    # Status is `recording`, not `finalizing`.
    with pytest.raises(SessionWrongState):
        commit_finalize_session(
            sess.session_id, "全收", repo_root=repo_with_skill,
        )
    abort_session(sess.session_id, keep_staging=False)


# ── `!include` detection / scenario_config round-trip ─────────────────


def test_scenario_yaml_does_not_use_include_tag_and_loads(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scenario_config uses bare yaml.safe_load (no !include support);
    we must inline assertions and the produced scenario.yaml must round-trip
    through ScenarioConfig.model_validate (load_scenario)."""
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    raw_text = Path(out["scenario_yaml_path"]).read_text(encoding="utf-8")
    assert "!include" not in raw_text  # inline-only branch confirmed

    # And the file actually loads via the production loader.
    cfg = load_scenario(Path(out["scenario_dir"]))
    assert cfg.query == "信息雷达"
    assert cfg.target_path == tp
    assert cfg.session_inject is not None
    assert cfg.session_inject.enabled is True
    assert cfg.session_inject.mock_rounds_dir == "mock_rounds/"
    # assertions inlined, ≥1 of them blocking tool_call_count
    assert any(
        a.kind == "tool_call_count" and a.blocking for a in cfg.assertions
    )


# ── warnings transparency ─────────────────────────────────────────────


def test_commit_finalize_surfaces_warnings_from_staging(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
        warnings_text=(
            "cc transcript not found; final_text.md left empty\n"
            "cc_session_id had 2 distinct ids; picked most-frequent\n"
        ),
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    assert len(out["warnings"]) == 2
    assert any("transcript" in w for w in out["warnings"])
    # warnings.txt not preserved in scenario dir (not part of contract)
    assert not (Path(out["scenario_dir"]) / "warnings.txt").exists()


# ── query / target_path ambiguity ──────────────────────────────────────


def test_commit_finalize_missing_query_returns_clarification(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Strip the `## 候选 query` section so draft has no fallback.
    draft = _default_draft_md().replace(
        "## 候选 query\n\n信息雷达\n\n",
        "## 候选 query\n\nTBD: 请用户给\n\n",
    )
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
        draft_md=draft,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": None,
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    assert out["action"] == "user_clarification"
    assert any("query" in q for q in out["questions"])
    # staging preserved → user can retry
    assert (sdir / "staging").is_dir()
    assert load_session(sid).status == "finalizing"
    abort_session(sid, keep_staging=False)


def test_commit_finalize_ambiguous_intents_returns_clarification(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": [],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": None,
        "target_path": None,
        "ambiguous_intents": [
            "用户说『差不多』，无法判断要保留哪些维度",
            "用户没给阈值",
        ],
    })

    out = commit_finalize_session(
        sid, "差不多就行，你看着办", repo_root=repo_with_skill,
    )
    assert out["action"] == "user_clarification"
    assert len(out["questions"]) == 2
    # staging preserved
    assert (sdir / "staging").is_dir()
    assert load_session(sid).status == "finalizing"
    abort_session(sid, keep_staging=False)


# ── target_path_sha256 fill ────────────────────────────────────────────


def test_commit_finalize_fills_target_path_sha256(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    tp = _make_target_path(repo_with_skill)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1", "D2", "F1", "F2"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "信息雷达",
        "target_path": tp,
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    meta = json.loads(
        (Path(out["scenario_dir"]) / "baseline" / "meta.json").read_text()
    )
    sha = meta["target_path_sha256"]
    assert isinstance(sha, str) and len(sha) == 64
    int(sha, 16)  # not raising = valid hex


def test_commit_finalize_empty_target_path_raises(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """target_path exists but contains zero files → EmptyTargetPath."""
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    # Make an empty dir under repo_with_skill (no files inside).
    empty_dir = repo_with_skill / "features/_evals/empty-tp"
    empty_dir.mkdir(parents=True, exist_ok=True)
    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "x",
        "target_path": "features/_evals/empty-tp",
        "ambiguous_intents": [],
    })

    with pytest.raises(EmptyTargetPath) as exc_info:
        commit_finalize_session(sid, "全收", repo_root=repo_with_skill)
    assert "empty-tp" in str(exc_info.value)


def test_commit_finalize_sha256_computed_before_backup(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """target_path self-referencing scenario_dir: sha must reflect pre-backup
    content, not sha256('') after backup moved everything away.

    Regression for the bug that produced sha256 = e3b0c44...b855 in meta.json
    when target_path pointed at skills/<skill>/evals/<scenario>/ itself.
    """
    sdir, sid = _make_finalizing_session(
        recorder_tmp=recorder_tmp,
        repo_with_skill=repo_with_skill,
    )
    # Pre-populate scenario_dir with some content so the self-ref hash is
    # meaningful (and ScenarioDirConflict path triggers a backup).
    scenario_dir = repo_with_skill / "skills" / "info-radar" / "evals" / "demo"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    (scenario_dir / "preexisting.txt").write_text(
        "old scenario content", encoding="utf-8",
    )

    _stub_feedback_llm(monkeypatch, {
        "keep_dimensions": ["D1"],
        "drop_dimensions": [],
        "threshold_overrides": {},
        "new_negative_cases": [],
        "query": "x",
        "target_path": "skills/info-radar/evals/demo",
        "ambiguous_intents": [],
    })

    out = commit_finalize_session(
        sid, "全收", repo_root=repo_with_skill, overwrite=True,
    )
    meta = json.loads(
        (Path(out["scenario_dir"]) / "baseline" / "meta.json").read_text()
    )
    sha = meta["target_path_sha256"]
    # sha256("") would be e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
    # If our reorder regresses, this assertion catches it.
    assert sha != (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ), "target_path_sha256 silently became sha256('') — step 9 reorder regressed"
    assert isinstance(sha, str) and len(sha) == 64
