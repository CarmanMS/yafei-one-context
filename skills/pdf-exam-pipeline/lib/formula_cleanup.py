"""清理 MinerU 导出的碎裂 LaTeX（去空格、规范括号）。"""
from __future__ import annotations

import re


def _collapse_math_spaces(tex: str) -> str:
    """去掉 _ { x } / ^ { x } / \operatorname * { } 等冗余空格。"""
    prev = None
    cur = tex
    patterns = [
        (r"\\operatorname\*\{\s*l\s*i\s*m\s*\}", r"\\lim"),
        (r"_\s*\{\s*", "_{"),
        (r"\^\s*\{\s*", "^{"),
        (r"\s*\}", "}"),
        (r"\\\s+", r"\\"),
        (r"\(\s+", "("),
        (r"\s+\)", ")"),
        (r"\{\s+", "{"),
        (r"\s+\}", "}"),
        (r"\s*,\s*", ", "),
        (r"\s*=\s*", " = "),
        (r"\\operatorname\s*\*\s*\{", r"\\operatorname*{"),
        (r"\\operatorname\s*\{", r"\\operatorname{"),
        (r"([A-Za-z])\s+\(", r"\1("),
        (r"\)\s+", ") "),
    ]
    while prev != cur:
        prev = cur
        for pat, rep in patterns:
            cur = re.sub(pat, rep, cur)
    return cur


def cleanup_latex_fragment(text: str) -> str:
    if not text or "$" not in text:
        return text.strip()

    def _fix_segment(seg: str) -> str:
        if not seg.strip():
            return seg
        return _collapse_math_spaces(seg)

    parts = re.split(r"(\$[^$]+\$)", text)
    out = []
    for p in parts:
        if p.startswith("$") and p.endswith("$"):
            inner = p[1:-1]
            out.append("$" + _collapse_math_spaces(inner) + "$")
        else:
            out.append(p)
    return "".join(out).strip()


def _close_unbalanced_math(stem: str) -> str:
    if stem.count("$") % 2 == 1:
        stem = re.sub(r"=\s*（\\quad）", r"$ = （\\quad）", stem, count=1)
        if stem.count("$") % 2 == 1:
            stem = re.sub(r"（\\quad）", r"$（\\quad）", stem, count=1)
    return stem


def cleanup_stem(stem: str) -> str:
    stem = cleanup_latex_fragment(stem)
    stem = re.sub(r"\(\s*\$\s*\)\s*\.?", r"（\\quad）。", stem)
    stem = re.sub(r"\(\s*\\begin\{array\}.*?\}\s*\)", r"(\\quad)", stem, flags=re.DOTALL)
    stem = re.sub(r"\(\s*\)", r"（\\quad）", stem)
    stem = re.sub(r"\(\s*\\quad\s*\)", r"（\\quad）", stem)
    stem = _close_unbalanced_math(stem)
    if not stem.endswith(("。", "．", ".", "）", ")")):
        if "（\\quad）" in stem or "(\\quad)" in stem:
            pass
        elif stem.rstrip().endswith("$"):
            stem = stem.rstrip() + "（\\quad）。"
    return stem.strip()
