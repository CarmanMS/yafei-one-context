"""rubric.load_or_generate 测试（generator 全部 mock，无 LLM 调用）。

真接 claude -p 测试在 M1.6（slow mark，默认 skip）。
"""
from unittest.mock import patch

import pytest

from one_context.usage_eval.rubric import (
    RUBRIC_FILENAME,
    load_or_generate,
    sha256_text,
    _force_correct_sha,
)


def test_sha256_text_stable():
    assert sha256_text("hello") == sha256_text("hello")
    assert sha256_text("hello") != sha256_text("hello!")


def test_load_or_generate_miss_calls_generator(tmp_path):
    """缓存 miss → 调 generator → 写盘 + sha 被 _force_correct_sha 主动覆盖（评审 D-01）"""
    skill_dir = tmp_path / "cover-prompt"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# cover-prompt\n\nDo X.\n")

    # mock 故意返回带 stub sha 的 fake，验证 _force_correct_sha 无条件覆盖
    fake = "---\nskill: cover-prompt\nskill_md_sha256: stub\n---\n# Rubric\n"
    with patch("one_context.usage_eval.rubric._spawn_rubric_llm", return_value=fake) as m:
        out = load_or_generate(skill_dir)
        assert m.called
    assert out.exists()
    assert out.name == RUBRIC_FILENAME
    text = out.read_text()
    assert "skill: cover-prompt" in text
    real_sha = sha256_text(skill_md.read_text())
    assert f"skill_md_sha256: {real_sha}" in text
    assert "skill_md_sha256: stub" not in text


def test_force_correct_sha_handles_missing_frontmatter():
    """LLM 完全没输出 frontmatter（极端）也要兜底"""
    out = _force_correct_sha("# Rubric\n\nbody only\n", "DEADBEEF", "foo")
    assert out.startswith("---\nskill: foo\nskill_md_sha256: DEADBEEF\n---")
    assert "# Rubric" in out


def test_load_or_generate_hit_skips_generator(tmp_path):
    skill_dir = tmp_path / "cover-prompt"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("v1")

    sha = sha256_text("v1")
    eval_dir = skill_dir / "__usage_eval"
    eval_dir.mkdir()
    rubric = eval_dir / RUBRIC_FILENAME
    rubric.write_text(f"---\nskill: cover-prompt\nskill_md_sha256: {sha}\n---\n# cached\n")

    with patch("one_context.usage_eval.rubric._spawn_rubric_llm") as m:
        load_or_generate(skill_dir)
        assert not m.called


def test_load_or_generate_sha_mismatch_regenerates(tmp_path):
    skill_dir = tmp_path / "cover-prompt"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("v2")

    eval_dir = skill_dir / "__usage_eval"
    eval_dir.mkdir()
    rubric = eval_dir / RUBRIC_FILENAME
    rubric.write_text("---\nskill: cover-prompt\nskill_md_sha256: STALE\n---\n# old\n")

    fresh = f"---\nskill: cover-prompt\nskill_md_sha256: {sha256_text('v2')}\n---\n# new\n"
    with patch("one_context.usage_eval.rubric._spawn_rubric_llm", return_value=fresh) as m:
        load_or_generate(skill_dir)
        assert m.called
    assert "# new" in rubric.read_text()


def test_load_or_generate_raises_when_skill_md_missing(tmp_path):
    import pytest
    skill_dir = tmp_path / "ghost"
    skill_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_or_generate(skill_dir)


def test_spawn_rubric_llm_strips_llm_frontmatter_and_adds_trusted(tmp_path):
    """LLM 若违规输出 frontmatter，必须被剥掉，由 Python 拼可信版"""
    from unittest.mock import patch
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# foo\n\nDo X.\n")

    # 模拟 _spawn_rubric_llm 的"剥+拼"行为：让 _spawn_rubric_llm 内部跑全流程，
    # 但拦截 subprocess.run 返回 LLM "违规" 输出（带 frontmatter）
    bad_llm_out = (
        "---\nskill: foo\nskill_md_sha256: WRONG_SHA\ngenerator_model: gpt-9\n---\n"
        "# Rubric: foo\n\n## fake body\n"
    )

    class FakeProc:
        returncode = 0
        stdout = bad_llm_out
        stderr = ""

    with patch("one_context.usage_eval.rubric.shutil.which", return_value="/usr/bin/claude"), \
         patch("one_context.usage_eval.rubric.subprocess.run", return_value=FakeProc()):
        from one_context.usage_eval.rubric import _spawn_rubric_llm
        out = _spawn_rubric_llm("# foo\n\nDo X.\n", "foo", model="claude-opus-4-7", timeout=10)

    # 必须有正确 sha + 正确 model；不能含 LLM 的 WRONG_SHA / gpt-9
    real_sha = sha256_text("# foo\n\nDo X.\n")
    assert f"skill_md_sha256: {real_sha}" in out
    assert "generator_model: claude-opus-4-7" in out
    assert "WRONG_SHA" not in out
    assert "gpt-9" not in out
    assert "# Rubric: foo" in out  # body 部分保留


# ─── slow 真测：默认 skip，pytest -m slow 才跑（消耗 token） ──────


@pytest.mark.skipif(__import__("shutil").which("claude") is None, reason="claude CLI 未安装")
@pytest.mark.slow
def test_spawn_rubric_llm_real_run(tmp_path):
    """真接 claude -p（约 $0.05），验证 LLM 输出能被 _extract_sha 解析。"""
    from one_context.usage_eval.rubric import _spawn_rubric_llm, _extract_sha
    skill_md = "# foo\n\nDo X when user asks Y.\n"
    out = _spawn_rubric_llm(skill_md, "foo")
    assert _extract_sha(out) == sha256_text(skill_md)
    assert "Rubric: foo" in out
    assert "dim_match" in out  # 5 维 rubric 必有这个 key

