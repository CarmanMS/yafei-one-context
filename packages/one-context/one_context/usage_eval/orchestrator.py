"""evaluate_session：把 parser / rubric / judge / report 串成完整链路。

主入口：``evaluate_session(repo_root, payload=None, sid=None, ...)``
- 优先用 hook payload 拿 transcript_path（评审 M-FIX-2）
- judge 失败 → 写 status: error 兜底产物（评审 S-02）
- 并发 ≤ max_workers（默认 4）跑 slot
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .judge import DimScore, JudgeResult, judge_with_retry
from .report import (
    RunArtifacts,
    atomic_append_index,
    index_line,
    write_run_artifacts,
)
from .rubric import load_or_generate, sha256_text
from .session_parser import (
    jsonl_from_payload,
    jsonl_path,
    parse_skill_slots,
    surrounding_turns,
)

log = logging.getLogger(__name__)


_ERROR_DIM_KEYS = (
    "dim_match", "dim_path", "dim_completeness", "dim_correction", "dim_satisfaction",
)


def _error_judge_result(reason: str) -> JudgeResult:
    """评审 S-02：judge 失败时的占位结果，保证 RunArtifacts 始终可构造。"""
    zero_dims = {k: DimScore(0.0, "judge unavailable") for k in _ERROR_DIM_KEYS}
    return JudgeResult(
        per_dimension=zero_dims, score=0.0, verdict="error",
        reason=reason, suggested_patch_md="",
    )


def _process_slot(
    repo_root: Path, sid: str, jsonl: Path, slot,
    judge_model: str, api_env: dict | None = None,
) -> dict | None:
    skill_dir = repo_root / "skills" / slot.skill_name
    if not skill_dir.exists():
        log.info("skip non-repo skill: %s", slot.skill_name)
        return None

    rubric_path = load_or_generate(skill_dir, extra_env=api_env)
    skill_md = (skill_dir / "SKILL.md").read_text()
    rubric_md = rubric_path.read_text()
    ctx = surrounding_turns(jsonl, slot.line_index, n=3)
    summary = (
        f"skill={slot.skill_name}\n"
        f"input={slot.tool_input}\n"
        f"result={str(slot.tool_result)[:2000]}\n"
    )
    surrounding_text = "\n".join(
        f"L{c['line']} [{c['type']}] {c['content_snippet']}" for c in ctx
    )

    run_id = f"{int(time.time())}-{sid[:8]}-{slot.slot_idx:03d}"
    slot_payload = {
        "skill": slot.skill_name,
        "input": slot.tool_input,
        "result": slot.tool_result,
        "line": slot.line_index,
    }
    rubric_sha = sha256_text(skill_md)

    # 评审 S-02：spec Phase 3 要求"重试失败仍写 report.md 标记 status: error"
    error_msg: str | None = None
    try:
        judge_res = judge_with_retry(
            skill_md=skill_md, rubric_md=rubric_md,
            slot_summary=summary, surrounding=surrounding_text, model=judge_model,
            extra_env=api_env,
        )
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        log.warning(
            "slot %s/%d judge failed after retries: %s",
            slot.skill_name, slot.slot_idx, error_msg,
        )
        judge_res = _error_judge_result(error_msg)

    art = RunArtifacts(
        skill_dir=skill_dir, skill_name=slot.skill_name,
        run_id=run_id, sid=sid, slot_idx=slot.slot_idx, judge=judge_res,
        slot_payload=slot_payload, rubric_sha=rubric_sha, judge_model=judge_model,
        status="error" if error_msg else "ok",
        error_message=error_msg,
    )
    out = write_run_artifacts(art)
    suggestion_count = (
        (judge_res.suggested_patch_md or "").count("## ") if judge_res.suggested_patch_md else 0
    )
    tools_used: list[str] = []  # M2 不抽，M5 再补
    atomic_append_index(
        skill_dir / "__usage_eval" / "INDEX.md",
        index_line(art, tools_used, suggestion_count),
    )
    log.info(
        "evaluated %s slot=%d status=%s score=%.2f -> %s",
        slot.skill_name, slot.slot_idx, art.status, judge_res.score, out,
    )
    return {
        "skill": slot.skill_name,
        "slot_idx": slot.slot_idx,
        "score": judge_res.score,
        "status": art.status,
        "out": str(out),
    }


def evaluate_session(
    *,
    repo_root: Path,
    sid: str | None = None,
    payload: dict | None = None,
    home: Path | None = None,
    judge_model: str = "GLM-5.1",
    max_workers: int = 4,
    api_env: dict | None = None,
) -> list[dict]:
    """M-FIX-2：优先用 hook payload 拿 transcript_path；缺则用 sid 反推。"""
    if payload is not None:
        jsonl = jsonl_from_payload(payload, home=home)
        sid = sid or payload.get("session_id", "unknown")
    elif sid:
        jsonl = jsonl_path(repo_root, sid, home=home)
    else:
        raise ValueError("evaluate_session requires either `payload` or `sid`")

    if not jsonl.exists():
        log.warning("jsonl not found: %s", jsonl)
        return []
    slots = parse_skill_slots(jsonl)
    log.info("found %d Skill tool_use slot(s) in %s", len(slots), jsonl.name)

    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [
            pool.submit(_process_slot, repo_root, sid, jsonl, s, judge_model, api_env)
            for s in slots
        ]
        for f in futs:
            try:
                r = f.result()
                if r is not None:
                    out.append(r)
            except Exception as e:
                log.exception("slot eval failed: %s", e)
    return out
