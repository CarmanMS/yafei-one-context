"""解析 cc session jsonl，抽 Skill 调用上下文。

主路径：cc SessionEnd hook 通过 stdin 给 JSON payload（含 transcript_path），
        daemon 直接读 transcript_path。
Fallback：cc 升级若不再给 transcript_path，回退用 cwd 反推（ADR-001 D-2）。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def jsonl_path(cwd: Path, sid: str, home: Path | None = None) -> Path:
    """根据 cc 命名约定推 jsonl 文件路径（fallback 用，主路径见 jsonl_from_payload）。

    算法（ADR-001 D-2）：cwd 绝对路径每个 ``/`` 替换为 ``-``，作为
    ``~/.claude/projects/`` 子目录名，jsonl 文件名为 ``<sid>.jsonl``。
    """
    home = home or Path.home()
    # 规范化绝对路径并去尾斜杠
    abs_cwd = str(cwd.resolve()).rstrip("/")
    project_dir_name = abs_cwd.replace("/", "-")
    return home / ".claude" / "projects" / project_dir_name / f"{sid}.jsonl"


def jsonl_from_payload(payload: dict, *, home: Path | None = None) -> Path:
    """M-FIX-2：优先用 hook stdin payload 给的 transcript_path；缺失则回退反推。

    Payload schema 见 ``features/core/skill-self-evolution-loop/probes/findings.md``。
    """
    tp = payload.get("transcript_path")
    if tp:
        return Path(tp)
    sid = payload.get("session_id")
    cwd = payload.get("cwd")
    if not sid or not cwd:
        raise ValueError(
            "payload missing both transcript_path and (session_id+cwd) — cannot locate jsonl"
        )
    return jsonl_path(Path(cwd), sid, home=home)


@dataclass
class SkillSlot:
    """单次 Skill tool_use 的现场：input / 配对 result / 行号 / 上下文。"""

    skill_name: str
    slot_idx: int  # 在本 session 内的全局序号
    tool_use_id: str
    tool_input: dict[str, Any]
    tool_result: Any  # 可能是 str / list[dict] / None
    line_index: int  # 在 jsonl 中的行号（1-based）
    surrounding_turns: list[dict] = field(default_factory=list)  # 留空，由 caller 补


def parse_skill_slots(jsonl_file: Path) -> list[SkillSlot]:
    """扫 jsonl 抽出所有 Skill tool_use + 配对的 tool_result。

    M-FIX-4：input.skill 单字段定位；缺则 warn + skip（cc schema 变化信号）。
    M-FIX-5：含 ':' 的 plugin skill 不在仓内 skills/，跳过。
    损坏行（非 JSON）跳过并落 warning。
    没配对到 result 的 tool_use 保留为 half-slot（result=None）。
    """
    if not jsonl_file.exists():
        log.warning("jsonl not found: %s", jsonl_file)
        return []

    events: list[dict] = []
    with jsonl_file.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append({"_lineno": lineno, **json.loads(raw)})
            except json.JSONDecodeError as e:
                log.warning("skipping malformed line %d: %s", lineno, e)

    pending: dict[str, SkillSlot] = {}
    slots: list[SkillSlot] = []
    slot_idx = 0
    for e in events:
        msg = e.get("message", {})
        content = msg.get("content", []) if isinstance(msg, dict) else []
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            if blk.get("type") == "tool_use" and blk.get("name") == "Skill":
                inp = blk.get("input", {}) or {}
                # M-FIX-4：单字段定位；缺则 warn + skip
                skill_name = inp.get("skill")
                if not skill_name:
                    log.warning(
                        "Skill tool_use missing input.skill at line %d "
                        "(cc schema may have changed): keys=%s",
                        e["_lineno"], sorted(inp.keys()),
                    )
                    continue
                # M-FIX-5：plugin skill 跳过（不在仓内 skills/）
                if ":" in skill_name:
                    log.debug("skip plugin skill (not in repo): %s", skill_name)
                    continue
                slot = SkillSlot(
                    skill_name=skill_name,
                    slot_idx=slot_idx,
                    tool_use_id=blk.get("id", ""),
                    tool_input=inp,
                    tool_result=None,
                    line_index=e["_lineno"],
                )
                pending[slot.tool_use_id] = slot
                slot_idx += 1
            elif blk.get("type") == "tool_result":
                tid = blk.get("tool_use_id")
                if tid in pending:
                    pending[tid].tool_result = blk.get("content")
                    slots.append(pending.pop(tid))

    # 没配对到 result 的也保留（half-slot）
    slots.extend(pending.values())
    slots.sort(key=lambda s: s.slot_idx)
    return slots


# content_snippet 截断长度——评审 U-03（待办，先抽常量以备后续）
SURROUNDING_CONTENT_MAX_CHARS = 200


def surrounding_turns(jsonl_file: Path, target_line: int, n: int = 3) -> list[dict]:
    """返回 target_line 前 n 条 + 后 n 条（不含 target 自己）的摘要。

    用于 judge 评 dim_correction（后续 turn 是否纠错）/ dim_satisfaction（用户是否抱怨）。
    每条返回 {"line": 行号, "type": event type, "content_snippet": 截断后的 content}。
    损坏行 / 不存在文件 → 返回空 list。
    """
    if not jsonl_file.exists():
        return []
    lines: list[tuple[int, dict]] = []
    with jsonl_file.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                lines.append((lineno, json.loads(raw)))
            except json.JSONDecodeError:
                continue

    before = [(ln, e) for (ln, e) in lines if target_line - n <= ln < target_line]
    after = [(ln, e) for (ln, e) in lines if target_line < ln <= target_line + n]
    out: list[dict] = []
    for ln, e in before + after:
        msg = e.get("message", {}) if isinstance(e, dict) else {}
        content = msg.get("content", "") if isinstance(msg, dict) else ""
        text = str(content)
        if len(text) > SURROUNDING_CONTENT_MAX_CHARS:
            text = text[:SURROUNDING_CONTENT_MAX_CHARS] + "..."
        out.append({"line": ln, "type": e.get("type"), "content_snippet": text})
    return out
