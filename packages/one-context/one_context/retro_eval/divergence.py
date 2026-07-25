"""文档-行为分叉检测：对照 SKILL.md 的约束句与实际执行轨迹。

本模块做**确定性初筛**：
  1. 从 SKILL.md 正则抽「不要X / 禁止X / 必须Y / 不得Z」约束句；
  2. 对每条约束，尽力从约束文本里识别「被禁止/被要求的工具或行为」，
     再到执行轨迹里找机器可判的证据（如约束含「Agent」→ 查轨迹是否出现 Agent 调用）。
最终 upheld/violated/obsolete/missing 四分类需 LLM 终判（SKILL.md 主线 Step 3），
本模块只给「约束 + 候选证据 + 机器初判」降低 LLM 负担、提供可追溯锚点。

见 tech_design.md §4.2。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 约束句模式：中文「不要/禁止/不得/必须/务必」+ markdown 强调
_CONSTRAINT_RE = re.compile(
    r"(?:\*\*)?(?P<kind>不要|禁止|不得|严禁|必须|务必|一定要|切勿|不能)(?P<body>[^。\n*]{2,60})"
)

# 约束文本里可能点名的「工具/行为」→ 在轨迹里对应的 tool 名（小写包含匹配）
_TOOL_HINTS = {
    "agent": ["Agent", "Task"],
    "task": ["Agent", "Task"],
    "派 agent": ["Agent", "Task"],
    "子 agent": ["Agent", "Task"],
    "subagent": ["Agent", "Task"],
    "webfetch": ["WebFetch", "webFetch", "mcp__codefusesearchmcp__webFetch"],
    "websearch": ["WebSearch", "mcp__codefusesearchmcp__webSearch"],
    "curl": ["Bash"],
    "脚本": ["Bash"],
    "批量": ["mcp__codefusesearchmcp__webFetch"],
}


@dataclass
class Constraint:
    """从 SKILL.md 抽出的一条约束。"""

    kind: str          # 不要 / 禁止 / 必须 ...
    text: str          # 约束原文（裁剪）
    line: int          # SKILL.md 行号
    polarity: str      # 'forbid'（不要/禁止类）| 'require'（必须类）
    referenced_tools: list[str] = field(default_factory=list)  # 约束点名的工具


_FORBID = {"不要", "禁止", "不得", "严禁", "切勿", "不能"}


def extract_constraints(skill_md: str) -> list[Constraint]:
    """从 SKILL.md 文本抽约束句。"""
    out: list[Constraint] = []
    for lineno, line in enumerate(skill_md.splitlines(), 1):
        for m in _CONSTRAINT_RE.finditer(line):
            kind = m.group("kind")
            body = m.group("body").strip(" *：:，,")
            if not body:
                continue
            text = (kind + body)[:80]
            polarity = "forbid" if kind in _FORBID else "require"
            low = text.lower()
            tools: list[str] = []
            for hint, names in _TOOL_HINTS.items():
                if hint in low:
                    for nm in names:
                        if nm not in tools:
                            tools.append(nm)
            out.append(Constraint(
                kind=kind, text=text, line=lineno,
                polarity=polarity, referenced_tools=tools,
            ))
    return out


def check_divergence(
    skill_md: str,
    scan_result: dict[str, Any],
) -> dict[str, Any]:
    """对每条约束，结合执行轨迹做机器初判。

    输出每条约束 + 候选证据 + machine_hint（供 LLM 终判参考）：
      - forbid 约束 + 点名工具在轨迹普遍出现  → machine_hint='possibly_violated_or_obsolete'
      - forbid 约束 + 点名工具从未出现        → machine_hint='likely_upheld'
      - require 约束                          → machine_hint='needs_llm'（落盘类需看 Output Contract）
      - 无法点名工具                          → machine_hint='needs_llm'
    """
    constraints = extract_constraints(skill_md)
    execs = scan_result.get("real_executions", [])
    n = len(execs)

    findings: list[dict] = []
    for c in constraints:
        evidence: list[str] = []
        machine_hint = "needs_llm"
        if c.referenced_tools:
            # 统计点名工具在多少 session 的 tool_chain 里出现
            hit_sessions = [
                t["short"] for t in execs
                if any(tool in t.get("tool_chain", []) for tool in c.referenced_tools)
            ]
            ratio = len(hit_sessions) / n if n else 0.0
            if c.polarity == "forbid":
                if hit_sessions:
                    evidence.append(
                        f"被禁止的工具 {c.referenced_tools} 在 {len(hit_sessions)}/{n} "
                        f"session 出现：{hit_sessions[:5]}"
                    )
                    # 普遍出现（≥半数）更可能是「约束已过时」，零星出现是「违反」
                    machine_hint = "possibly_obsolete" if ratio >= 0.5 else "possibly_violated"
                else:
                    evidence.append(f"被禁止的工具 {c.referenced_tools} 在所有 session 均未出现")
                    machine_hint = "likely_upheld"
        findings.append({
            "constraint": c.text,
            "kind": c.kind,
            "polarity": c.polarity,
            "skill_md_line": c.line,
            "referenced_tools": c.referenced_tools,
            "evidence": evidence,
            "machine_hint": machine_hint,
        })

    return {
        "skill": scan_result.get("skill"),
        "constraints_found": len(constraints),
        "real_execution_count": n,
        "findings": findings,
        "note": (
            "machine_hint 仅为确定性初判；upheld/violated/obsolete/missing 的最终判定"
            "需 LLM 结合负面后果综合判断（见 SKILL.md Step 3）。"
            "'missing'（高频问题但约束没写）无法由本模块发现，须 LLM 从失败聚合中识别。"
        ),
    }
