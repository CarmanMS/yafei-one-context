"""构建后验证：版式锚点 + 题目结构。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .yaml_io import load_yaml

REQUIRED_TEX_MARKERS = [
    "浙江外国语学院",
    "装",
    "订",
    "线",
    "MATH1029",
    "单项选择题",
    "题号",
    "阅卷人",
    "A．",
    "B．",
    "C．",
    "D．",
]


def verify_tex(tex_path: Path, yaml_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not tex_path.is_file():
        return [f"MISSING tex: {tex_path}"]
    text = tex_path.read_text(encoding="utf-8")
    for marker in REQUIRED_TEX_MARKERS:
        if marker not in text:
            errors.append(f"MISSING marker in tex: {marker}")

    q_stems: list[str] = []
    if yaml_path and yaml_path.is_file():
        data = load_yaml(yaml_path)
        for sec in data.get("sections", []):
            for q in sec.get("questions", []):
                stem = q.get("stem", "")
                if stem:
                    q_stems.append(stem[:24])
        expect_n = len(q_stems)
        if expect_n and text.count("\n\n\\noindent ") < expect_n:
            errors.append(f"FAIL question blocks < {expect_n}")
        for i, snippet in enumerate(q_stems[:1], start=1):
            token = re.sub(r"\\[a-zA-Z]+", "", snippet)[:12]
            if token and token not in text.replace(" ", ""):
                # 宽松：至少应含题号
                if f"{i}．" not in text and f"{i}." not in text:
                    errors.append(f"FAIL missing question {i}")

    if len(re.findall(r"\d+．", text)) < 5:
        errors.append("FAIL expected >=5 numbered questions")
    return errors


def verify_pdf(pdf_path: Path, min_bytes: int = 20000) -> list[str]:
    errors: list[str] = []
    if not pdf_path.is_file():
        return [f"MISSING pdf: {pdf_path}"]
    if pdf_path.stat().st_size < min_bytes:
        errors.append(f"FAIL pdf too small: {pdf_path.stat().st_size}")
    return errors


def verify_all(tex: Path, pdf: Path, yaml_path: Path | None = None) -> list[str]:
    errors = verify_tex(tex, yaml_path)
    errors.extend(verify_pdf(pdf))
    return errors


def verify_or_raise(tex: Path, pdf: Path, yaml_path: Path | None = None) -> None:
    errors = verify_all(tex, pdf, yaml_path)
    if errors:
        raise RuntimeError("VERIFY FAIL:\n  " + "\n  ".join(errors))
