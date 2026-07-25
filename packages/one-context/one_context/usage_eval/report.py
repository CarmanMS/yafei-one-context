"""渲染 report.md / suggested_patch.md / slot.json + atomic append INDEX.md。

产物落 ``skills/<name>/__usage_eval/<runId>/``；INDEX.md 用 fcntl.flock
保证多 daemon 进程并发 append 不撕裂（评审 S-04：必须用进程而非线程验原子性）。
"""
from __future__ import annotations

import datetime as _dt
import fcntl
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .judge import JudgeResult


@dataclass
class RunArtifacts:
    skill_dir: Path
    skill_name: str
    run_id: str
    sid: str
    slot_idx: int
    judge: JudgeResult
    slot_payload: dict[str, Any]
    rubric_sha: str
    judge_model: str = "claude-sonnet-4-6"
    # 评审 S-02：spec Phase 3 要求 report.md 携带 status: error / ok
    status: str = "ok"
    error_message: str | None = None


def write_run_artifacts(a: RunArtifacts) -> Path:
    out = a.skill_dir / "__usage_eval" / a.run_id
    out.mkdir(parents=True, exist_ok=True)

    fm_lines = [
        "---",
        f"skill: {a.skill_name}",
        f"runId: {a.run_id}",
        f"sid: {a.sid}",
        f"slot_idx: {a.slot_idx}",
        f"status: {a.status}",
        f"score: {a.judge.score:.2f}",
        f"verdict: {a.judge.verdict}",
        f"judge_model: {a.judge_model}",
        f"rubric_sha256: {a.rubric_sha}",
        f"ts: {_dt.datetime.now(_dt.timezone.utc).isoformat()}",
    ]
    if a.error_message:
        fm_lines.append(f"error_message: {a.error_message}")
    fm_lines.append("---")

    body = [
        "",
        f"# 评估：{a.skill_name} @ {a.run_id}",
        "",
        f"## 总评（score: {a.judge.score:.2f}, verdict: {a.judge.verdict}）",
        "",
        a.judge.reason,
        "",
        "## 各维度分",
        "",
        "| 维度 | 分 | 理由 |",
        "|---|---|---|",
    ]
    for dim_key, dim in a.judge.per_dimension.items():
        body.append(f"| {dim_key} | {dim.score:.2f} | {dim.reason} |")
    body += [
        "",
        "## 改进建议",
        "",
        "详见同目录 [suggested_patch.md](./suggested_patch.md)",
        "",
        "[原始数据](./slot.json)",
        "",
    ]
    (out / "report.md").write_text("\n".join(fm_lines + body))

    # suggested_patch.md
    patch = f"# SKILL.md 改进建议（{a.skill_name} @ {a.run_id}）\n\n"
    patch += (
        a.judge.suggested_patch_md
        or "_本次评估未给出改进建议（评分 ≥ 0.9 或 judge 留空 / 失败）_\n"
    )
    (out / "suggested_patch.md").write_text(patch)

    # slot.json
    (out / "slot.json").write_text(
        json.dumps(a.slot_payload, ensure_ascii=False, indent=2, default=str)
    )
    return out


def atomic_append_index(index_path: Path, line: str) -> None:
    """flock 串行化 append；多进程安全（评审 S-04）。"""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            if not line.endswith("\n"):
                line = line + "\n"
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def index_line(a: RunArtifacts, tools_used: list[str], suggestion_count: int) -> str:
    """INDEX.md 行格式（含 status 列，评审 S-02）。

    trend.py 用正则 LINE_RE_V2 解析；旧版无 status 列由 LINE_RE_V1 兼容。
    """
    return (
        f"{a.run_id} | {a.judge.score:.2f} | {a.judge.verdict:<10} "
        f"| status={a.status:<5} | sid={a.sid} | tools={','.join(tools_used) or '-'} "
        f"| suggestions={suggestion_count}"
    )
