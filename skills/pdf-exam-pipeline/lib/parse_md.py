"""MinerU Markdown → questions YAML（浙江外国语学院期末卷第 1 页）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .formula_cleanup import cleanup_latex_fragment, cleanup_stem
from .yaml_io import dump_yaml

CHOICE_SPLIT = re.compile(r"(?<![A-Za-z])([A-D])[\.．]\s*")


def find_md(path: str | Path) -> Path:
    p = Path(path)
    if p.is_dir():
        mds = sorted(p.rglob("*.md"))
        if not mds:
            raise FileNotFoundError(f"no md under {p}")
        return mds[0]
    if "*" in str(path):
        import glob

        hits = sorted(glob.glob(str(path), recursive=True))
        if not hits:
            raise FileNotFoundError(path)
        return Path(hits[0])
    return p


def _parse_meta(text: str) -> dict[str, Any]:
    course = re.search(
        r"课程名称[\\_]*([^课程编号]+)课程编号[\\_]*([A-Z0-9]+)试卷类型\s*([A-Z])",
        text,
    )
    year = re.search(r"(20\d{2})[～~]\s*(20\d{2})", text)
    return {
        "school": "浙江外国语学院",
        "title": "期末考试试卷",
        "course_name": course.group(1).strip() if course else "高等数学C（二）",
        "course_id": course.group(2) if course else "MATH1029",
        "paper_type": course.group(3) if course else "A",
        "academic_year": f"{year.group(1)}-{year.group(2)}-2" if year else "2023-2024-2",
        "page_label": "（第 1 页共 4 页）",
        "total_points": 100,
    }


def _parse_section(text: str) -> tuple[str, str]:
    m = re.search(r"##\s*(.+)", text)
    if not m:
        return "一、单项选择题", "（本大题说明）"
    line = m.group(1).strip().rstrip(".")
    if "（" in line:
        title, rest = line.split("（", 1)
        instruction = "（" + rest
        if not instruction.endswith("。"):
            instruction += "。"
        return title.strip(), instruction
    return line, ""


def _split_questions_blob(blob: str) -> list[str]:
    blob = blob.strip()
    # MinerU 常把 4．、5．粘在上一题同一行
    blob = re.sub(r"(?<=\S)\s*(\d+)[\.．]\s*", r"\n\1．", blob)
    chunks = re.split(r"(?=(?:^|\n)\s*\d+[\.．])", blob)
    return [c.strip() for c in chunks if c.strip() and re.match(r"^\d+", c.strip())]


def _parse_one_question(chunk: str, default_points: int = 3) -> dict[str, Any]:
    m = re.match(r"^(\d+)[\.．]\s*(.*)$", chunk, re.DOTALL)
    if not m:
        raise ValueError(f"bad question chunk: {chunk[:80]!r}")
    qnum = int(m.group(1))
    rest = m.group(2).strip()
    parts = CHOICE_SPLIT.split(rest)
    if len(parts) < 9:
        raise ValueError(f"q{qnum}: expected A-D choices, got {len(parts)} parts")
    stem = cleanup_stem(parts[0])
    choices: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        label = parts[i]
        body = cleanup_latex_fragment(parts[i + 1].strip())
        choices[label] = body
    for label in "ABCD":
        choices.setdefault(label, "")
    total = sum(len(choices[k]) for k in "ABCD")
    layout = "inline" if all(len(choices[k]) < 36 for k in "ABCD") and total < 100 else "multiline"
    return {
        "id": f"q{qnum}",
        "points": default_points,
        "stem": stem,
        "choices": choices,
        "choice_layout": layout,
        "answer": "",
        "figure": None,
    }


def parse_mineru_md(text: str) -> dict[str, Any]:
    title, instruction = _parse_section(text)
    sec_pos = text.find("##")
    body = text[sec_pos:] if sec_pos >= 0 else text
    body = re.sub(r"^##[^\n]+\n", "", body, count=1)
    questions: list[dict[str, Any]] = []
    for chunk in _split_questions_blob(body):
        try:
            questions.append(_parse_one_question(chunk))
        except ValueError:
            continue
    if not questions:
        raise ValueError("no questions parsed from MinerU MD")
    return {
        "meta": _parse_meta(text),
        "sections": [
            {
                "id": "sec-1",
                "title": title,
                "instruction": instruction,
                "questions": questions,
            }
        ],
        "_source": "mineru-md",
    }


def parse_md_file(md_path: Path) -> dict[str, Any]:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    return parse_mineru_md(text)


def write_parsed_md(md_path: Path, out_path: Path) -> dict[str, Any]:
    data = parse_md_file(md_path)
    dump_yaml(data, out_path)
    return data
