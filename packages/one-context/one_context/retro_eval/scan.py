"""跨会话回溯检索：给定 skill 名，从本机 cc 会话语料找出其真实执行轨迹。

与 ``usage_eval`` 的区别：那条是 SessionEnd hook 实时评单个会话；本模块是人主动
发起的**跨会话回溯**——扫所有历史 jsonl，区分「真实执行」与「仅文本提及」，
聚合反复出现的问题。见 features/core/skill-retrospective-evolution/tech_design.md。

复用 ``usage_eval.session_parser.parse_skill_slots`` 抓强信号（Skill tool_use）；
弱信号（产物落盘 / 特征工具链）本模块自实现，因为 info-radar 等 skill 多由
自然语言触发，并无显式 Skill tool_use（48 提及 → 4 真实执行的判定关键）。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from one_context.usage_eval.session_parser import parse_skill_slots

log = logging.getLogger(__name__)

# cc 会话根候选，按优先级探测（codefuse 封装版在前，标准版在后）
SESSION_ROOTS = (
    Path.home() / ".codefuse" / "engine" / "cc" / "projects",
    Path.home() / ".claude" / "projects",
)


def detect_session_roots(home: Path | None = None) -> list[Path]:
    """返回本机存在的 cc 会话根目录（可能两者都在）。"""
    roots = (
        (home / ".codefuse" / "engine" / "cc" / "projects",
         home / ".claude" / "projects")
        if home else SESSION_ROOTS
    )
    return [r for r in roots if r.is_dir()]


def project_dir_name(cwd: Path) -> str:
    """cc 把 cwd 绝对路径的每个 '/' 换成 '-' 作为 projects 子目录名。"""
    return str(cwd.resolve()).rstrip("/").replace("/", "-")


def candidate_jsonls(
    skill: str,
    *,
    scope: str = "current-project",
    cwd: Path | None = None,
    home: Path | None = None,
    since_days: int | None = None,
    max_sessions: int | None = None,
) -> list[Path]:
    """grep 出提及 skill 的候选 jsonl（粗筛，不区分真实/提及）。

    scope='current-project' 仅扫当前 cwd 对应的 projects 子目录（默认，隐私优先）；
    scope='all' 扫全部子目录。
    """
    cwd = cwd or Path(os.getcwd())
    roots = detect_session_roots(home)
    if not roots:
        log.warning("no cc session root found under %s", [str(r) for r in SESSION_ROOTS])
        return []

    search_dirs: list[Path] = []
    if scope == "current-project":
        name = project_dir_name(cwd)
        for root in roots:
            d = root / name
            if d.is_dir():
                search_dirs.append(d)
    else:
        search_dirs = roots

    needle = skill.encode()
    hits: list[tuple[float, Path]] = []
    cutoff = None
    if since_days is not None:
        # mtime 截断；避免 import time（测试可注入），用文件 stat 自比
        import time as _t
        cutoff = _t.time() - since_days * 86400
    for d in search_dirs:
        for f in sorted(d.glob("*.jsonl")):
            try:
                st = f.stat()
            except OSError:
                continue
            if cutoff is not None and st.st_mtime < cutoff:
                continue
            # 流式扫，命中即停（大文件不全载入）
            try:
                with f.open("rb") as fh:
                    if any(needle in line for line in fh):
                        hits.append((st.st_mtime, f))
            except OSError as e:
                log.warning("cannot read %s: %s", f, e)

    hits.sort(key=lambda t: t[0], reverse=True)  # 新会话在前
    files = [f for _, f in hits]
    if max_sessions is not None:
        files = files[:max_sessions]
    return files


@dataclass
class Signature:
    """skill 的「执行特征」声明，来自 skills/<name>/.retro-signature.yaml（可选）。"""

    artifact_globs: list[str] = field(default_factory=list)  # 产物路径 glob（Write 命中即算执行）
    source_domains: list[str] = field(default_factory=list)  # 特征 fetch 域名
    min_fetch_hits: int = 3  # 连续命中多少次源域名才算弱信号

    @classmethod
    def load(cls, skill: str, repo_root: Path) -> "Signature":
        path = repo_root / "skills" / skill / ".retro-signature.yaml"
        if not path.is_file():
            return cls()
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as e:
            log.warning("bad signature yaml %s: %s", path, e)
            return cls()
        return cls(
            artifact_globs=list(data.get("artifact_globs", [])),
            source_domains=list(data.get("source_domains", [])),
            min_fetch_hits=int(data.get("min_fetch_hits", 3)),
        )


@dataclass
class ExecutionTrace:
    """单个真实执行 session 的抽取结果（精简，不含原文整段）。"""

    session_id: str
    jsonl: str  # 文件路径（短号取 stem 前 8）
    verdict: str  # 'strong' | 'weak'
    evidence: list[str]  # 判定依据（如 "Skill tool_use", "wrote production/info-radar/04-report.md"）
    skill_tool_uses: int  # 显式 Skill 调用次数
    artifact_writes: list[str]  # 命中 signature 的产物落盘路径
    fetch_hits: int  # 命中源域名的 fetch 次数
    tool_chain: list[str]  # 工具调用名序列（去重压缩，供人工/ subagent 参考）

    @property
    def short(self) -> str:
        return Path(self.jsonl).stem[:8]


def _iter_tool_uses(jsonl_file: Path):
    """yield (lineno, name, input_dict) for every tool_use block."""
    try:
        with jsonl_file.open() as f:
            for lineno, raw in enumerate(f, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    e = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg = e.get("message", {})
                content = msg.get("content", []) if isinstance(msg, dict) else []
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        yield lineno, blk.get("name", ""), (blk.get("input") or {})
    except OSError as e:
        log.warning("cannot read %s: %s", jsonl_file, e)


def classify(jsonl_file: Path, skill: str, sig: Signature) -> ExecutionTrace | None:
    """判定单个 jsonl 是否为 skill 的真实执行；非执行（仅提及）返回 None。

    强信号：parse_skill_slots 命中 input.skill == skill。
    弱信号：① Write 命中 signature.artifact_globs；② fetch 命中 source_domains ≥ min_fetch_hits。
    """
    # 强信号（复用 usage_eval）
    strong_slots = [s for s in parse_skill_slots(jsonl_file) if s.skill_name == skill]

    # 弱信号扫描
    artifact_writes: list[str] = []
    fetch_hits = 0
    chain: list[str] = []
    for _lineno, name, inp in _iter_tool_uses(jsonl_file):
        if name and (not chain or chain[-1] != name):
            chain.append(name)
        if name in ("Write", "Edit") and sig.artifact_globs:
            fp = str(inp.get("file_path", ""))
            if fp and any(fnmatch(fp, g) or _glob_suffix_match(fp, g)
                          for g in sig.artifact_globs):
                artifact_writes.append(fp)
        if name in ("WebFetch", "webFetch", "mcp__codefusesearchmcp__webFetch") and sig.source_domains:
            urls = _extract_urls(inp)
            if any(any(dom in u for dom in sig.source_domains) for u in urls):
                fetch_hits += 1

    evidence: list[str] = []
    verdict: str | None = None
    if strong_slots:
        verdict = "strong"
        evidence.append(f"{len(strong_slots)}× Skill tool_use (input.skill={skill})")
    weak_ok = bool(artifact_writes) or fetch_hits >= sig.min_fetch_hits
    if weak_ok:
        verdict = verdict or "weak"
        if artifact_writes:
            evidence.append(f"wrote {len(artifact_writes)} signature artifact(s)")
        if fetch_hits >= sig.min_fetch_hits:
            evidence.append(f"{fetch_hits}× fetch hit source domains")

    if verdict is None:
        return None  # 仅提及，非真实执行

    return ExecutionTrace(
        session_id="",  # 由 caller 从首行补全（避免再解析一遍）
        jsonl=str(jsonl_file),
        verdict=verdict,
        evidence=evidence,
        skill_tool_uses=len(strong_slots),
        artifact_writes=artifact_writes,
        fetch_hits=fetch_hits,
        tool_chain=chain,
    )


def _glob_suffix_match(file_path: str, glob: str) -> bool:
    """支持 'production/info-radar/*.json' 这种相对后缀匹配绝对路径尾部。"""
    if "/" not in glob:
        return False
    return fnmatch(file_path, "*/" + glob) or fnmatch(file_path, glob)


def _extract_urls(inp: dict[str, Any]) -> list[str]:
    """从 fetch 类工具的 input 里挖 URL（单 url 字段 / urlList 数组都兼容）。"""
    out: list[str] = []
    if isinstance(inp.get("url"), str):
        out.append(inp["url"])
    ul = inp.get("urlList")
    if isinstance(ul, list):
        out.extend(str(u) for u in ul)
    return out


def _first_session_id(jsonl_file: Path) -> str:
    try:
        with jsonl_file.open() as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    e = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                sid = e.get("sessionId")
                if sid:
                    return sid
    except OSError:
        pass
    return jsonl_file.stem


def scan(
    skill: str,
    *,
    repo_root: Path,
    scope: str = "current-project",
    cwd: Path | None = None,
    home: Path | None = None,
    since_days: int | None = None,
    max_sessions: int | None = None,
) -> dict[str, Any]:
    """主入口：检索 + 真实执行判定，返回可 JSON 序列化的结果。"""
    sig = Signature.load(skill, repo_root)
    candidates = candidate_jsonls(
        skill, scope=scope, cwd=cwd, home=home,
        since_days=since_days, max_sessions=max_sessions,
    )
    real: list[ExecutionTrace] = []
    errors: list[dict[str, str]] = []
    for f in candidates:
        try:
            trace = classify(f, skill, sig)
        except Exception as e:  # noqa: BLE001 — 单文件失败不应中断全局
            errors.append({"jsonl": str(f), "reason": repr(e)})
            continue
        if trace is not None:
            trace.session_id = _first_session_id(f)
            real.append(trace)

    return {
        "skill": skill,
        "scope": scope,
        "signature_present": bool(sig.artifact_globs or sig.source_domains),
        "sessions_scanned": len(candidates),
        "real_executions": [
            {
                "session_id": t.session_id,
                "short": t.short,
                "jsonl": t.jsonl,
                "verdict": t.verdict,
                "evidence": t.evidence,
                "skill_tool_uses": t.skill_tool_uses,
                "artifact_writes": t.artifact_writes,
                "fetch_hits": t.fetch_hits,
                "tool_chain": t.tool_chain,
            }
            for t in real
        ],
        "real_execution_count": len(real),
        "errors": errors,
    }
