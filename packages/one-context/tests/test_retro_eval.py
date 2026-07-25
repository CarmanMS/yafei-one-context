"""Tests for retro_eval.scan — 跨会话回溯检索 + 真实执行判定。

判定逻辑用合成 jsonl fixture 锁定（不依赖本机真实会话语料，后者会随时间增长）。
见 features/core/skill-retrospective-evolution/tech_design.md §4.1。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.retro_eval.scan import (
    Signature,
    classify,
    detect_session_roots,
    project_dir_name,
    scan,
)


# ---------------------------------------------------------------------------
# jsonl fixture helpers
# ---------------------------------------------------------------------------

def _assistant_tool_use(name: str, inp: dict, tid: str = "t1") -> dict:
    return {
        "type": "assistant",
        "sessionId": "sess-fixture",
        "message": {"content": [{"type": "tool_use", "name": name, "id": tid, "input": inp}]},
    }


def _user_text(text: str) -> dict:
    return {"type": "user", "sessionId": "sess-fixture", "message": {"content": text}}


def _write_jsonl(path: Path, events: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


@pytest.fixture()
def sig() -> Signature:
    return Signature(
        artifact_globs=["production/info-radar/*.json", "production/info-radar/*.md"],
        source_domains=["github.com/trending", "hacker-news.firebaseio.com"],
        min_fetch_hits=3,
    )


# ---------------------------------------------------------------------------
# classify — 真实执行 vs 仅提及
# ---------------------------------------------------------------------------

def test_mention_only_returns_none(tmp_path, sig):
    """只在文本里聊到 skill 名，无 Skill 调用 / 无产物 / 无源 fetch → 非执行。"""
    f = _write_jsonl(tmp_path / "a.jsonl", [
        _user_text("帮我看看 info-radar 这个 skill 怎么样"),
        _assistant_tool_use("Read", {"file_path": "/x/SKILL.md"}),
    ])
    assert classify(f, "info-radar", sig) is None


def test_strong_signal_skill_tool_use(tmp_path, sig):
    """显式 Skill tool_use(input.skill 命中) → strong。"""
    f = _write_jsonl(tmp_path / "b.jsonl", [
        _assistant_tool_use("Skill", {"skill": "info-radar"}),
    ])
    t = classify(f, "info-radar", sig)
    assert t is not None and t.verdict == "strong"
    assert t.skill_tool_uses == 1


def test_weak_signal_artifact_write(tmp_path, sig):
    """无 Skill 调用，但 Write 命中产物 glob → weak。"""
    f = _write_jsonl(tmp_path / "c.jsonl", [
        _user_text("扫文章"),
        _assistant_tool_use("Write", {"file_path": "/repo/production/info-radar/04-report.md"}),
    ])
    t = classify(f, "info-radar", sig)
    assert t is not None and t.verdict == "weak"
    assert t.artifact_writes == ["/repo/production/info-radar/04-report.md"]


def test_weak_signal_fetch_threshold(tmp_path, sig):
    """fetch 命中源域名达到 min_fetch_hits → weak；低于阈值且无产物 → None。"""
    events = [_assistant_tool_use("WebFetch", {"url": "https://github.com/trending"}, tid=f"t{i}")
              for i in range(3)]
    t = classify(_write_jsonl(tmp_path / "d.jsonl", events), "info-radar", sig)
    assert t is not None and t.verdict == "weak" and t.fetch_hits == 3

    # 只命中 2 次 → 不足阈值 → 仅提及
    events2 = [_assistant_tool_use("WebFetch", {"url": "https://github.com/trending"}, tid=f"u{i}")
               for i in range(2)]
    assert classify(_write_jsonl(tmp_path / "e.jsonl", events2), "info-radar", sig) is None


def test_fetch_batch_urllist_counts(tmp_path, sig):
    """批量 webFetch(urlList) 也应计数(info-radar 真实行为是批量拉)。"""
    f = _write_jsonl(tmp_path / "f.jsonl", [
        _assistant_tool_use("mcp__codefusesearchmcp__webFetch", {
            "urlList": ["https://github.com/trending",
                        "https://hacker-news.firebaseio.com/v0/topstories.json"],
        }),
    ])
    t = classify(f, "info-radar", sig)
    # 单次批量调用算 1 次 fetch_hit（不足阈值3），无产物 → None
    assert t is None or t.fetch_hits == 1


def test_strong_beats_weak_in_evidence(tmp_path, sig):
    """既有 Skill 调用又有产物 → verdict=strong，但 evidence 两者都记。"""
    f = _write_jsonl(tmp_path / "g.jsonl", [
        _assistant_tool_use("Skill", {"skill": "info-radar"}, tid="s1"),
        _assistant_tool_use("Write", {"file_path": "/r/production/info-radar/01-raw-fetched.json"}, tid="w1"),
    ])
    t = classify(f, "info-radar", sig)
    assert t.verdict == "strong"
    assert t.artifact_writes  # 产物也被记录
    assert any("Skill tool_use" in e for e in t.evidence)


def test_other_skill_not_matched(tmp_path, sig):
    """另一个 skill 的 Skill 调用不应算作 info-radar 的执行。"""
    f = _write_jsonl(tmp_path / "h.jsonl", [
        _assistant_tool_use("Skill", {"skill": "gitsync"}),
    ])
    assert classify(f, "info-radar", sig) is None


def test_no_signature_falls_back_to_strong_only(tmp_path):
    """无 signature 时，仅强信号可判定；产物/ fetch 无从命中。"""
    empty = Signature()
    f = _write_jsonl(tmp_path / "i.jsonl", [
        _assistant_tool_use("Write", {"file_path": "/r/production/info-radar/04-report.md"}),
    ])
    assert classify(f, "info-radar", empty) is None  # 无 signature → 产物不算数

    f2 = _write_jsonl(tmp_path / "j.jsonl", [_assistant_tool_use("Skill", {"skill": "info-radar"})])
    assert classify(f2, "info-radar", empty).verdict == "strong"


# ---------------------------------------------------------------------------
# Signature.load
# ---------------------------------------------------------------------------

def test_signature_load_from_repo(tmp_path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / ".retro-signature.yaml").write_text(
        "artifact_globs:\n  - 'out/*.json'\nsource_domains:\n  - example.com\nmin_fetch_hits: 5\n"
    )
    sig = Signature.load("demo", tmp_path)
    assert sig.artifact_globs == ["out/*.json"]
    assert sig.source_domains == ["example.com"]
    assert sig.min_fetch_hits == 5


def test_signature_load_missing_returns_empty(tmp_path):
    sig = Signature.load("nope", tmp_path)
    assert sig.artifact_globs == [] and sig.source_domains == []


# ---------------------------------------------------------------------------
# scan — 端到端（合成 projects 目录）
# ---------------------------------------------------------------------------

def test_scan_current_project_isolates_cwd(tmp_path):
    """scan 在合成 home 下，只扫当前 cwd 对应的 projects 子目录。"""
    home = tmp_path / "home"
    cwd = tmp_path / "work" / "myrepo"
    cwd.mkdir(parents=True)
    proj_dir = home / ".claude" / "projects" / project_dir_name(cwd)
    proj_dir.mkdir(parents=True)

    # 一个真实执行（Skill 调用）+ 一个仅提及
    _write_jsonl(proj_dir / "real.jsonl", [_assistant_tool_use("Skill", {"skill": "info-radar"})])
    _write_jsonl(proj_dir / "mention.jsonl", [_user_text("info-radar 是啥")])

    result = scan("info-radar", repo_root=tmp_path, scope="current-project", cwd=cwd, home=home)
    # 两个文件都含 "info-radar" 字串 → 都是 grep 候选；但 mention 判 None
    assert result["sessions_scanned"] == 2
    assert result["real_execution_count"] == 1
    assert result["real_executions"][0]["verdict"] == "strong"


def test_detect_session_roots_empty(tmp_path):
    assert detect_session_roots(home=tmp_path) == []


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def test_aggregate_failure_structural_vs_sporadic(tmp_path):
    """失败信号出现在 ≥2 session → structural；仅 1 → sporadic。"""
    from one_context.retro_eval.aggregate import aggregate

    def _result(text, is_err=False):
        return {"type": "user", "sessionId": "s",
                "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "x", "is_error": is_err, "content": text}]}}

    # 两个 session 都有 Cloudflare 拦截 → structural；一个有 timeout → sporadic
    f1 = _write_jsonl(tmp_path / "s1.jsonl", [_result("Just a moment... Cloudflare challenge")])
    f2 = _write_jsonl(tmp_path / "s2.jsonl", [_result("error: Cloudflare blocked")])
    f3 = _write_jsonl(tmp_path / "s3.jsonl", [_result("request timed out")])

    scan_result = {
        "skill": "demo",
        "real_executions": [
            {"short": "s1", "jsonl": str(f1), "verdict": "weak", "tool_chain": ["WebFetch"], "artifact_writes": ["a.json"]},
            {"short": "s2", "jsonl": str(f2), "verdict": "weak", "tool_chain": ["WebFetch"], "artifact_writes": []},
            {"short": "s3", "jsonl": str(f3), "verdict": "strong", "tool_chain": ["Skill"], "artifact_writes": []},
        ],
    }
    agg = aggregate(scan_result)
    assert "blocked" in agg["failures"]["structural"]      # 2 session
    assert agg["failures"]["structural"]["blocked"]["sessions"] == 2
    assert "timeout" in agg["failures"]["sporadic"]         # 1 session
    assert agg["output_contract"]["sessions_with_artifacts"] == 1
    assert agg["verdict_distribution"] == {"weak": 2, "strong": 1}


def test_aggregate_no_originals_leaked(tmp_path):
    """聚合输出不得包含 jsonl 原文（隐私守护）。"""
    from one_context.retro_eval.aggregate import aggregate

    secret = "SENSITIVE_USER_SECRET_12345"
    f = _write_jsonl(tmp_path / "s.jsonl", [
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "x", "content": f"{secret} request timed out"}]}},
    ])
    scan_result = {"skill": "d", "real_executions": [
        {"short": "s", "jsonl": str(f), "verdict": "weak", "tool_chain": [], "artifact_writes": []}]}
    agg = aggregate(scan_result)
    assert secret not in json.dumps(agg, ensure_ascii=False)  # 只记 kind/次数，不记原文


# ---------------------------------------------------------------------------
# divergence
# ---------------------------------------------------------------------------

def test_extract_constraints_finds_forbid_and_require():
    from one_context.retro_eval.divergence import extract_constraints

    md = (
        "# Skill\n"
        "- **不要派 Agent / Task 去做单源解析**。\n"
        "- 每次扫描必须落盘 04-report.md。\n"
        "- 这是普通说明，无约束。\n"
    )
    cs = extract_constraints(md)
    kinds = {c.kind for c in cs}
    assert "不要" in kinds and "必须" in kinds
    forbid = [c for c in cs if c.kind == "不要"][0]
    assert "Agent" in forbid.referenced_tools  # 点名工具被识别


def test_divergence_forbidden_tool_widely_used_is_obsolete(tmp_path):
    """约束『不要派 Agent』但 Agent 在多数 session 出现 → possibly_obsolete。"""
    from one_context.retro_eval.divergence import check_divergence

    md = "- **不要派 Agent 去解析**。\n"
    scan_result = {"skill": "d", "real_executions": [
        {"short": "a", "tool_chain": ["Agent", "Bash"]},
        {"short": "b", "tool_chain": ["Agent", "Write"]},
    ]}
    d = check_divergence(md, scan_result)
    f = d["findings"][0]
    assert f["machine_hint"] == "possibly_obsolete"
    assert f["evidence"]


def test_divergence_forbidden_tool_never_used_is_upheld(tmp_path):
    from one_context.retro_eval.divergence import check_divergence

    md = "- **不要派 Agent 去解析**。\n"
    scan_result = {"skill": "d", "real_executions": [
        {"short": "a", "tool_chain": ["WebFetch", "Bash"]},
    ]}
    d = check_divergence(md, scan_result)
    assert d["findings"][0]["machine_hint"] == "likely_upheld"
