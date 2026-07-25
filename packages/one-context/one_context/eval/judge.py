"""LLM rubric judge — the only assert type.

Spawns `claude -p` with a cheap model (default haiku) to score the
provider output against the rubric. Per ISS-016, the cache key is

    sha256(
        criteria_text + "\n---CRIT-OUTPUT---\n" +
        final_text    + "\n---TEXT-ARTI---\n" +
        json.dumps(sorted([{"path": p, "sha256": s} for p, s in artifacts]))
    )

Excluded from cache key: tool_calls (contains tmp paths that vary per
runId), duration_ms / timestamp / requested_model / actual_model. Model
drift is surfaced through baseline diff, not by busting the cache.

The judge itself is also subprocess-based and replaceable for tests via
`ONECXT_EVAL_JUDGE_REPLAY_DIR` (see provider.py for the mirror env).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_JUDGE_MODEL = "claude-haiku-4-5"
# R-12a (design §16.7.17): default raised from 300s → 600s because Kimi-K2.6
# occasionally stalls on ~11KB prompts (rubric + DENIED summary + BASELINE
# artifact heads). Override via ONECXT_EVAL_JUDGE_TIMEOUT_MS (ms).
JUDGE_TIMEOUT_MS_DEFAULT = 600_000

# R-12b (design §16.7.17): cap each artifact head pasted into the judge
# prompt so the total prompt stays small enough to avoid model stalls.
# Source `run.json` still keeps the full head; this only trims what the
# judge LLM sees. Override via ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES;
# set to 0 to disable truncation.
JUDGE_ARTIFACT_HEAD_BYTES_DEFAULT = 1500


def _resolve_judge_timeout_ms() -> int:
    raw = os.environ.get("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "").strip()
    if not raw:
        return JUDGE_TIMEOUT_MS_DEFAULT
    try:
        v = int(raw)
    except ValueError:
        return JUDGE_TIMEOUT_MS_DEFAULT
    return v if v > 0 else JUDGE_TIMEOUT_MS_DEFAULT


def _resolve_artifact_head_bytes() -> int:
    """Returns max bytes for each artifact head in the judge prompt.

    0 means "no truncation". Negative or non-int env → fall back to default.
    """
    raw = os.environ.get("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "").strip()
    if not raw:
        return JUDGE_ARTIFACT_HEAD_BYTES_DEFAULT
    try:
        v = int(raw)
    except ValueError:
        return JUDGE_ARTIFACT_HEAD_BYTES_DEFAULT
    return v if v >= 0 else JUDGE_ARTIFACT_HEAD_BYTES_DEFAULT


def _truncate_head(head: str, max_bytes: int) -> str:
    """Byte-budget head truncation safe across utf-8 boundaries.

    max_bytes == 0 → no-op. When truncated, append a single marker line.
    """
    if max_bytes <= 0:
        return head
    b = head.encode("utf-8")
    if len(b) <= max_bytes:
        return head
    trimmed = b[:max_bytes].decode("utf-8", errors="ignore")
    return trimmed.rstrip() + "\n... (truncated)"


_RUBRIC_PROMPT_TEMPLATE = """你是一名严格的评分员。根据下面的 criteria 评估 output 是否合格，输出严格 JSON：
{{ "pass": bool, "score": 0.0-1.0, "reason": "为什么 pass/fail，引用 output 中具体片段" }}

只输出这一个 JSON 对象，不要任何额外解释、代码块标记或前后缀文本。

# criteria

{criteria}

# output

## final_text

{final_text}

## tool_calls 摘要（仅供参考，不计入评分）

> 标 `[DENIED]` 前缀的条目是 cc 发出但被 `--disallowedTools` 当场拒绝的试调，**没有产生任何真实副作用**（无网络请求、无文件写入、无进程派生）。请勿将这些 deny 试调当作"逃逸"或"违规"——它们等价于"未执行的尝试"。判分时只计未标 [DENIED] 的真调。

{tool_calls_summary}

## artifacts

> 标 `[BASELINE]` 的文件是 session_inject 录制时的真实产物（已完成的上一轮交付物），等同任务**已完成**——请勿因 cc 本次没重新产出这些文件就触发 "pipeline 未完成 / 缺失产物" 类硬性失败。`[CC-WRITE]` 才是 cc 本次新写的文件。判分时把 BASELINE + CC-WRITE 并作"任务产物全集"看待。

{artifacts_block}
"""


def merge_rubric(skill_default: str | None, scenario_override: str | None) -> str:
    """Combine skill default rubric with scenario override.

    If both present, scenario rubric is treated as additive — appended after
    a separator. If only one is present, it's used verbatim.
    """
    parts = [s.strip() for s in (skill_default, scenario_override) if s and s.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[0] + "\n\n# scenario-specific additions\n\n" + parts[1]


def _format_tool_calls(tool_calls: list[dict]) -> str:
    if not tool_calls:
        return "(none)"
    lines = []
    for i, tc in enumerate(tool_calls, 1):
        name = tc.get("name", "?")
        inp = tc.get("input") or {}
        # Shrink to interesting keys only
        keys = ("file_path", "path", "command", "url", "pattern")
        digest = " ".join(f"{k}={inp[k]!r}" for k in keys if k in inp)
        # R-9 治理 (design §16.7.11): mark cc-attempted-but-denied calls
        # so the judge LLM doesn't count them as real side effects (e.g.
        # `Bash curl evil.com [DENIED]` is NOT a net-egress violation —
        # cc tried but --disallowedTools blocked it).
        prefix = "[DENIED] " if tc.get("is_error") else ""
        lines.append(f"  {i}. {prefix}{name} {digest}".rstrip())
    return "\n".join(lines)


def _format_artifacts(artifacts: list[dict]) -> str:
    if not artifacts:
        return "(none)"
    max_bytes = _resolve_artifact_head_bytes()
    lines = []
    for art in artifacts:
        path = art.get("path", "?")
        size = art.get("size", 0)
        head = _truncate_head((art.get("head") or "").rstrip(), max_bytes)
        # R-10a 治理 (design §16.7.13): mark source so the judge knows
        # whether a file is cc's fresh write (source=produced, default
        # when missing) or the recorded baseline (source=baseline).
        # The replay assumption is "baseline files represent the
        # already-completed prior turn"; judge should NOT trip a
        # pipeline-completeness rule just because cc didn't re-produce
        # them this turn.
        src = art.get("source", "produced")
        src_tag = "[BASELINE]" if src == "baseline" else "[CC-WRITE]"
        lines.append(f"### {src_tag} {path} ({size}B)\n```\n{head}\n```")
    return "\n\n".join(lines)


def render_prompt(
    criteria: str,
    final_text: str,
    tool_calls: list[dict],
    artifacts: list[dict],
    *,
    provider_status_notice: str | None = None,
) -> str:
    body = _RUBRIC_PROMPT_TEMPLATE.format(
        criteria=criteria.strip(),
        final_text=(final_text or "").strip() or "(empty)",
        tool_calls_summary=_format_tool_calls(tool_calls),
        artifacts_block=_format_artifacts(artifacts),
    )
    # R-5 治理 D (design §16.7.5): runner prepends a status notice when
    # provider failed but blocking assertions all passed, so the judge
    # can still score partial progress instead of being skipped entirely.
    if provider_status_notice and provider_status_notice.strip():
        return (
            "# provider 状态提示（评分前必读）\n\n"
            + provider_status_notice.strip()
            + "\n\n---\n\n"
            + body
        )
    return body


def cache_key(
    criteria: str,
    final_text: str,
    artifacts: list[dict],
) -> str:
    """Hash the inputs that *should* invalidate the judge cache.

    Includes criteria full text, final_text full, and a sorted list of
    (path, sha256). Excludes tool_calls (would pin to runId-specific tmp
    paths), timing, and model identifiers.
    """
    arts_norm = sorted(
        [{"path": a.get("path", ""), "sha256": a.get("sha256", "")} for a in artifacts],
        key=lambda d: d["path"],
    )
    payload = (
        (criteria or "").strip()
        + "\n---CRIT-OUTPUT---\n"
        + (final_text or "").strip()
        + "\n---TEXT-ARTI---\n"
        + json.dumps(arts_norm, ensure_ascii=False, sort_keys=True)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class JudgeResult:
    pass_: bool
    score: float
    reason: str
    model: str
    cached: bool = False
    raw: str = ""


def _parse_judge_output(raw: str) -> tuple[bool, float, str]:
    """Extract the first JSON object from `raw` and validate fields.

    Tolerates models that wrap output in ```json ... ``` fences or add
    extra prose before/after.
    """
    text = raw.strip()
    # Strip code fences if present.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Find first balanced {...}.
    start = text.find("{")
    if start < 0:
        raise ValueError(f"judge output has no JSON object: {raw!r}")
    depth = 0
    end = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text[start:], start=start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise ValueError(f"judge output JSON not balanced: {raw!r}")

    obj = json.loads(text[start:end])
    if "pass" not in obj or "score" not in obj:
        raise ValueError(f"judge output missing required fields: {obj!r}")
    return bool(obj["pass"]), float(obj["score"]), str(obj.get("reason", ""))


def _resolve_settings_path() -> str | None:
    """Resolve the `--settings` value for spawning claude (Stage 2.X.2).

    Resolution order, mirrors evals/providers/claude-code.js:
      1. ``$ONECXT_CLAUDE_SETTINGS`` (caller override; empty string disables)
      2. CCD2 backup path (project default for evals on this host)

    Set ``ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT=1`` to fall back to claude's
    own default settings (no ``--settings`` flag added).
    """
    DEFAULT_SETTINGS_PATH = (
        f"{os.environ.get('HOME', '')}/.claude/settings.json.backup.20260529_153816"
    )
    disable_default = os.environ.get("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT") == "1"
    settings_path = os.environ.get("ONECXT_CLAUDE_SETTINGS")
    if settings_path is None and not disable_default:
        settings_path = DEFAULT_SETTINGS_PATH
    return settings_path or None


def _spawn_judge(prompt: str, model: str) -> str:
    """Default judge backend: spawn `claude -p`. Replaceable via env."""
    replay_dir = os.environ.get("ONECXT_EVAL_JUDGE_REPLAY_DIR")
    if replay_dir:
        # Replay mode — look up by sha256(prompt) → file content.
        key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        path = Path(replay_dir) / f"{key}.txt"
        if not path.is_file():
            raise RuntimeError(
                f"judge replay miss: {key} (set ONECXT_EVAL_JUDGE_RECORD_DIR to record)"
            )
        return path.read_text(encoding="utf-8")

    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--permission-mode", "bypassPermissions",
    ]
    # Stage 2.X.2: mirror provider's settings resolution so judge spawn uses
    # the same gateway (CCD2 backup by default). See evals/providers/claude-code.js
    # for the contract.
    settings_path = _resolve_settings_path()
    if settings_path:
        cmd.extend(["--settings", settings_path])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=_resolve_judge_timeout_ms() / 1000,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"judge spawn failed (rc={result.returncode}): {result.stderr.strip()[:500]}"
        )
    out = result.stdout

    # Optional record mode for tests.
    record_dir = os.environ.get("ONECXT_EVAL_JUDGE_RECORD_DIR")
    if record_dir:
        rd = Path(record_dir)
        rd.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        (rd / f"{key}.txt").write_text(out, encoding="utf-8")

    return out


def evaluate(
    *,
    criteria: str,
    final_text: str,
    tool_calls: list[dict],
    artifacts: list[dict],
    cache_dir: Path,
    model: str = DEFAULT_JUDGE_MODEL,
    provider_status_notice: str | None = None,
) -> JudgeResult:
    """Run the rubric judge with cache.

    Args:
        criteria: merged rubric text.
        final_text: provider final text.
        tool_calls: provider tool_calls (used in prompt only, not cache key).
        artifacts: list of {path, sha256, size, head}; (path, sha256)
            participates in the cache key.
        cache_dir: where to store/read judge response cache.
        model: judge model id.
        provider_status_notice: R-5 治理 D (design §16.7.5). When the
            runner detects a non-ok provider state with P3 all passed,
            it passes a short notice describing the partial run; the
            notice prepends the prompt so the judge can score progress
            instead of being skipped. Not part of cache_key — when
            final_text differs (it almost always does for timeout vs.
            ok runs) the cache naturally separates the two cases.
    """
    if not criteria.strip():
        # No rubric → cannot judge. Treat as fail with explicit reason so
        # the author knows to add one.
        return JudgeResult(
            pass_=False,
            score=0.0,
            reason="no rubric configured (skill eval.yaml default_rubric "
            "or scenario.yaml rubric)",
            model=model,
            cached=False,
            raw="",
        )

    key = cache_key(criteria, final_text, artifacts)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"

    if cache_file.is_file():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        return JudgeResult(
            pass_=bool(cached["pass"]),
            score=float(cached["score"]),
            reason=str(cached.get("reason", "")),
            model=str(cached.get("model", model)),
            cached=True,
            raw=str(cached.get("raw", "")),
        )

    prompt = render_prompt(
        criteria, final_text, tool_calls, artifacts,
        provider_status_notice=provider_status_notice,
    )
    raw = _spawn_judge(prompt, model)
    pass_, score, reason = _parse_judge_output(raw)

    cache_file.write_text(
        json.dumps(
            {
                "pass": pass_,
                "score": score,
                "reason": reason,
                "model": model,
                "raw": raw,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return JudgeResult(
        pass_=pass_, score=score, reason=reason, model=model, cached=False, raw=raw
    )
