"""Skill 跨会话回溯进化 — 从历史 cc 会话语料聚合诊断单个 skill。

人主动发起的跨会话回溯分析（区别于 usage_eval 的实时单会话评估）。
见 features/core/skill-retrospective-evolution/。
"""
from one_context.retro_eval.aggregate import aggregate
from one_context.retro_eval.divergence import check_divergence, extract_constraints
from one_context.retro_eval.scan import ExecutionTrace, Signature, scan

__all__ = [
    "scan", "Signature", "ExecutionTrace",
    "aggregate", "check_divergence", "extract_constraints",
]
