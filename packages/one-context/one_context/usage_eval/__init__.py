"""Skill usage self-evaluation loop.

会话结束后自动评估本会话用过的仓内 skill；AI 自学 rubric；
输出 markdown 报告 + SKILL.md 改进建议（人工 gate）。

See features/core/skill-self-evolution-loop/spec.md for the design.
See features/core/skill-self-evolution-loop/adr/001-hook-and-jsonl-path.md
for M0 实证决策（hook=SessionEnd, jsonl 主路径=stdin payload.transcript_path,
Skill 定位字段=input.skill）。
"""
