"""每 skill 的 AI 自学评估 rubric：load 或生成（哈希校验失效重生）。

frontmatter 由 Python 拼装（不信任 LLM 输出 placeholder，评审 D-05）：
- skill: <name>
- skill_md_sha256: <真实 sha>
- generated_at / generator_model / schema_version

真实 LLM 调用见 ``_spawn_rubric_llm``（M1.6 接 claude -p）。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import os
import re
import shutil
import subprocess
from importlib.resources import files as _files
from pathlib import Path

log = logging.getLogger(__name__)

RUBRIC_FILENAME = "RUBRIC.md"
SHA_RE = re.compile(r"^skill_md_sha256:\s*(\S+)\s*$", re.MULTILINE)
SHA_LINE_RE = re.compile(r"^skill_md_sha256:.*$", re.MULTILINE)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_sha(rubric_text: str) -> str | None:
    m = SHA_RE.search(rubric_text)
    return m.group(1) if m else None


RUBRIC_GENERATOR_MODEL_DEFAULT = "GLM-5.1"  # 统一走 GLM-5.1（通过 env ANTHROPIC_MODEL，绕过 --model 白名单）
RUBRIC_GENERATOR_TIMEOUT_SEC = 180


def _spawn_rubric_llm(
    skill_md: str,
    skill_name: str,
    *,
    model: str = RUBRIC_GENERATOR_MODEL_DEFAULT,
    timeout: int = RUBRIC_GENERATOR_TIMEOUT_SEC,
    extra_env: dict | None = None,
) -> str:
    """生成 RUBRIC.md 完整文本（frontmatter 由 Python 拼装，body 由 LLM 产出）。

    评审 D-05：不再让 LLM 字面输出 placeholder——prompt 明令 LLM 只输出 body，
    Python 端：(1) 即便 LLM 错误地输出 frontmatter 也强行剥掉，(2) 主动拼接可信
    frontmatter。
    评审 D-06：stdin=DEVNULL 防 hang。

    model 通过 env ANTHROPIC_MODEL 透传（不走 --model flag），绕过 cc 内部白名单。
    extra_env 通常含 ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL（从 --api-settings 加载）。
    """
    if shutil.which("claude") is None:
        raise RuntimeError("claude CLI not found on PATH; cannot generate rubric")

    prompt_tmpl = (
        _files("one_context.usage_eval.prompts")
        .joinpath("rubric_generator.md")
        .read_text(encoding="utf-8")
    )
    prompt = prompt_tmpl.replace("{skill_name}", skill_name).replace("{skill_md}", skill_md)

    sub_env = {**os.environ}
    if extra_env:
        sub_env.update(extra_env)
    sub_env["ANTHROPIC_MODEL"] = model

    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,  # 评审 D-06
        timeout=timeout,
        env=sub_env,
    )
    if proc.returncode != 0:
        # 同 judge：claude CLI 把 API error 写 stdout 不是 stderr
        raise RuntimeError(
            f"rubric generator failed (rc={proc.returncode}): "
            f"stderr={proc.stderr[:300]!r} stdout={proc.stdout[:300]!r}"
        )
    body = proc.stdout.lstrip()

    # LLM 即便错误地输出了 frontmatter 也强行剥掉
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].lstrip("\n")

    # Python 拼装可信 frontmatter
    fm = (
        "---\n"
        f"skill: {skill_name}\n"
        f"skill_md_sha256: {sha256_text(skill_md)}\n"
        f"generated_at: {_dt.datetime.now(_dt.timezone.utc).isoformat()}\n"
        f"generator_model: {model}\n"
        "schema_version: 1\n"
        "---\n\n"
    )
    return fm + body


def _force_correct_sha(rubric_text: str, expected_sha: str, skill_name: str) -> str:
    """无条件用真实 sha 覆盖 frontmatter 中的字段；缺则补；无 frontmatter 则前置一份。

    评审 D-01/D-05：不信任 LLM 输出的 sha placeholder，主动覆盖。
    """
    if SHA_LINE_RE.search(rubric_text):
        return SHA_LINE_RE.sub(f"skill_md_sha256: {expected_sha}", rubric_text, count=1)
    if rubric_text.lstrip().startswith("---"):
        return rubric_text.replace("---\n", f"---\nskill_md_sha256: {expected_sha}\n", 1)
    return f"---\nskill: {skill_name}\nskill_md_sha256: {expected_sha}\n---\n\n{rubric_text}"


def load_or_generate(skill_dir: Path, *, extra_env: dict | None = None) -> Path:
    """返回 RUBRIC.md Path（必要时生成 / 重生）。

    缓存 hit 条件：`skills/<name>/__usage_eval/RUBRIC.md` 存在且其 frontmatter 的
    `skill_md_sha256` 与当前 SKILL.md 哈希一致。否则调 _spawn_rubric_llm 重生。

    extra_env 透传给 LLM subprocess（含 ANTHROPIC_AUTH_TOKEN/BASE_URL 等）。
    """
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")
    skill_md = skill_md_path.read_text()
    expected_sha = sha256_text(skill_md)

    eval_dir = skill_dir / "__usage_eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    rubric_path = eval_dir / RUBRIC_FILENAME

    if rubric_path.exists():
        cached_sha = _extract_sha(rubric_path.read_text())
        if cached_sha == expected_sha:
            log.debug("rubric cache hit: %s", rubric_path)
            return rubric_path
        log.info(
            "rubric sha mismatch (cached=%s expected=%s), regenerating",
            cached_sha, expected_sha,
        )

    rubric_text = _spawn_rubric_llm(skill_md, skill_dir.name, extra_env=extra_env)
    rubric_text = _force_correct_sha(rubric_text, expected_sha, skill_dir.name)
    rubric_path.write_text(rubric_text)
    return rubric_path
