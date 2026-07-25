"""LLM cheap judge：对单次 Skill 调用按 rubric 5 维打分。

`judge_skill_call` 拿到 LLM 输出后 JSON 容错抽取 → JudgeResult dataclass。
`judge_with_retry` 1/4/16s 指数退避，最多 3 次。
真实 LLM 调用 `_spawn_judge_llm` 在 M2.2 接 claude -p（stdin DEVNULL +
单 slot 5min timeout + env 覆盖，S-01 + D-06）。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from importlib.resources import files as _files

log = logging.getLogger(__name__)

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
RAW_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)


@dataclass
class DimScore:
    score: float
    reason: str


@dataclass
class JudgeResult:
    per_dimension: dict[str, DimScore]
    score: float
    verdict: str
    reason: str
    suggested_patch_md: str


# 评审 S-01：单 slot 5min 硬上限，env 可覆盖（spec.md Phase 3 验收口径）
DEFAULT_SLOT_TIMEOUT_SEC = 300
SLOT_TIMEOUT_ENV = "ONECXT_USAGE_EVAL_SLOT_TIMEOUT"
DEFAULT_JUDGE_MODEL = "GLM-5.1"  # 评测统一走 GLM-5.1（通过 env ANTHROPIC_MODEL 透传，绕过 cc --model 白名单）


def _resolve_slot_timeout(default: int = DEFAULT_SLOT_TIMEOUT_SEC) -> int:
    raw = os.environ.get(SLOT_TIMEOUT_ENV, "").strip()
    if not raw:
        return default
    try:
        return max(30, int(raw))
    except ValueError:
        return default


def _extract_json(raw: str) -> dict:
    m = JSON_BLOCK_RE.search(raw)
    candidate = m.group(1) if m else None
    if candidate is None:
        m = RAW_OBJECT_RE.search(raw)
        candidate = m.group(1) if m else None
    if candidate is None:
        raise ValueError(f"no JSON object in judge output: {raw[:200]}")
    return json.loads(candidate)


def _spawn_judge_llm(
    *, skill_md, rubric_md, slot_summary, surrounding, model,
    timeout=None, extra_env: dict | None = None,
) -> str:
    """Spawn `claude -p` cheap judge。评审 D-06 stdin DEVNULL + S-01 单 slot timeout。

    model 通过 env ANTHROPIC_MODEL 透传（不走 `--model` flag），绕过 cc 内部
    模型白名单——这样 GLM-5.1 等非官方 model 可用，endpoint 路由由 antchat 处理。
    extra_env 通常含 ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL（从 --api-settings 加载）。
    """
    if shutil.which("claude") is None:
        raise RuntimeError("claude CLI not found")
    timeout = timeout or _resolve_slot_timeout()
    tmpl = (
        _files("one_context.usage_eval.prompts")
        .joinpath("judge.md")
        .read_text(encoding="utf-8")
    )
    prompt = (
        tmpl.replace("{skill_md}", skill_md)
        .replace("{rubric_md}", rubric_md)
        .replace("{slot_summary}", slot_summary)
        .replace("{surrounding}", surrounding)
    )
    sub_env = {**os.environ}
    if extra_env:
        sub_env.update(extra_env)
    sub_env["ANTHROPIC_MODEL"] = model
    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        env=sub_env,
    )
    if proc.returncode != 0:
        # claude CLI 把 API error（如 "400 该模型需要授权"）写到 stdout 不是 stderr，
        # 必须两边都带上才能定位根因
        raise RuntimeError(
            f"judge LLM rc={proc.returncode}: "
            f"stderr={proc.stderr[:300]!r} stdout={proc.stdout[:300]!r}"
        )
    return proc.stdout


def judge_skill_call(
    *,
    skill_md: str,
    rubric_md: str,
    slot_summary: str,
    surrounding: str,
    model: str = DEFAULT_JUDGE_MODEL,
    timeout: int | None = None,
    extra_env: dict | None = None,
) -> JudgeResult:
    raw = _spawn_judge_llm(
        skill_md=skill_md, rubric_md=rubric_md,
        slot_summary=slot_summary, surrounding=surrounding,
        model=model, timeout=timeout, extra_env=extra_env,
    )
    obj = _extract_json(raw)
    per_dim = {
        k: DimScore(score=float(v["score"]), reason=v.get("reason", ""))
        for k, v in obj["per_dimension"].items()
    }
    return JudgeResult(
        per_dimension=per_dim,
        score=float(obj["score"]),
        verdict=obj["verdict"],
        reason=obj.get("reason", ""),
        suggested_patch_md=obj.get("suggested_patch_md", ""),
    )


def judge_with_retry(
    *,
    skill_md: str,
    rubric_md: str,
    slot_summary: str,
    surrounding: str,
    model: str = DEFAULT_JUDGE_MODEL,
    max_retries: int = 3,
    extra_env: dict | None = None,
) -> JudgeResult:
    """spec Phase 3：1/4/16s 指数退避，最多 3 次。仍失败抛 RuntimeError。"""
    delays = [1, 4, 16]
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            return judge_skill_call(
                skill_md=skill_md, rubric_md=rubric_md,
                slot_summary=slot_summary, surrounding=surrounding,
                model=model, extra_env=extra_env,
            )
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                log.warning(
                    "judge attempt %d failed: %s; retrying in %ds",
                    attempt + 1, e, delays[attempt],
                )
                time.sleep(delays[attempt])
    raise RuntimeError(f"judge failed after {max_retries} attempts") from last_err
