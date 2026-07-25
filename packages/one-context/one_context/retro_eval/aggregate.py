"""跨 session 确定性聚合：把 scan 出的真实执行轨迹铺开，统计反复出现的信号。

确定性部分（频次统计、失败关键词扫描、产物落盘率）放这里；
LLM 综合判断留给 SKILL.md 主线。见 tech_design.md §3、§4.2。
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# 失败信号关键词（tool_result 文本 / is_error）
_FAIL_PATTERNS = {
    "timeout": re.compile(r"timeout|timed out|ETIMEDOUT", re.I),
    "blocked": re.compile(r"Cloudflare|challenge|403|forbidden|captcha|just a moment", re.I),
    "connection": re.compile(r"Connection closed|ECONNREFUSED|-32000|network error", re.I),
    "parse_error": re.compile(r"JSONDecodeError|failed to parse|invalid json|unexpected token", re.I),
    "empty": re.compile(r"no results|empty|returned nothing|0 articles", re.I),
}

# fetch 类工具名
_FETCH_TOOLS = {"WebFetch", "webFetch", "mcp__codefusesearchmcp__webFetch"}


def _result_text(content: Any) -> str:
    """tool_result.content 可能是 str / list[{type:text,text:...}] / None → 统一成文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(str(blk.get("text", "")) or json.dumps(blk, ensure_ascii=False))
            else:
                parts.append(str(blk))
        return "\n".join(parts)
    return str(content)


@dataclass
class SessionFailures:
    """单 session 内扫到的失败信号摘要。"""

    short: str
    fail_kinds: Counter = field(default_factory=Counter)  # kind -> 次数
    error_tool_results: int = 0  # is_error=True 的 tool_result 数


def _scan_session_failures(jsonl_file: Path, short: str) -> SessionFailures:
    """扫一个 session 的所有 tool_result，统计失败信号（不保留原文）。"""
    sf = SessionFailures(short=short)
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
                msg = e.get("message", {})
                content = msg.get("content", []) if isinstance(msg, dict) else []
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                        continue
                    if blk.get("is_error"):
                        sf.error_tool_results += 1
                    text = _result_text(blk.get("content"))
                    for kind, pat in _FAIL_PATTERNS.items():
                        if pat.search(text):
                            sf.fail_kinds[kind] += 1
    except OSError as e:
        log.warning("cannot read %s: %s", jsonl_file, e)
    return sf


def aggregate(scan_result: dict[str, Any]) -> dict[str, Any]:
    """对 scan() 的结果做跨 session 聚合。

    输入：scan() 返回的 dict（含 real_executions）。
    输出：可 JSON 序列化的聚合结论，**不含任何 jsonl 原文**。
    """
    execs = scan_result.get("real_executions", [])
    n = len(execs)

    # 1. verdict 分布
    verdict_dist = Counter(t["verdict"] for t in execs)

    # 2. Output Contract 落盘率：有 artifact_writes 的 session 占比
    with_artifacts = sum(1 for t in execs if t.get("artifact_writes"))

    # 3. 工具链高频模式：统计每种工具出现在多少个 session（不是总次数）
    tool_session_freq: Counter = Counter()
    for t in execs:
        for tool in set(t.get("tool_chain", [])):
            tool_session_freq[tool] += 1

    # 4. 跨 session 失败信号聚合
    fail_kind_sessions: Counter = Counter()  # kind -> 出现该失败的 session 数
    fail_kind_total: Counter = Counter()     # kind -> 总次数
    sessions_with_errors = 0
    per_session_fail: list[dict] = []
    for t in execs:
        jsonl = Path(t["jsonl"])
        sf = _scan_session_failures(jsonl, t["short"])
        if sf.error_tool_results:
            sessions_with_errors += 1
        for kind, cnt in sf.fail_kinds.items():
            fail_kind_sessions[kind] += 1
            fail_kind_total[kind] += cnt
        if sf.fail_kinds or sf.error_tool_results:
            per_session_fail.append({
                "short": sf.short,
                "fail_kinds": dict(sf.fail_kinds),
                "error_tool_results": sf.error_tool_results,
            })

    # 5. 反复失败模式：出现在 ≥2 个 session 的失败 kind = 结构性
    structural = {k: {"sessions": fail_kind_sessions[k], "total": fail_kind_total[k]}
                  for k in fail_kind_sessions if fail_kind_sessions[k] >= 2}
    sporadic = {k: {"sessions": fail_kind_sessions[k], "total": fail_kind_total[k]}
                for k in fail_kind_sessions if fail_kind_sessions[k] == 1}

    return {
        "skill": scan_result.get("skill"),
        "real_execution_count": n,
        "verdict_distribution": dict(verdict_dist),
        "output_contract": {
            "sessions_with_artifacts": with_artifacts,
            "sessions_total": n,
            "artifact_rate": round(with_artifacts / n, 2) if n else 0.0,
        },
        "tool_session_frequency": dict(tool_session_freq.most_common()),
        "failures": {
            "sessions_with_error_results": sessions_with_errors,
            "structural": structural,  # ≥2 session：值得改 skill
            "sporadic": sporadic,      # 仅 1 session：偶发
            "per_session": per_session_fail,
        },
    }
