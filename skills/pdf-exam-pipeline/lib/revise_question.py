"""单题替换：只改指定题，其余保持。"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .yaml_io import dump_yaml, load_yaml

# 内置：第 1 题由定积分换为二重积分（C（二）A 卷试点）
Q1_DOUBLE_INTEGRAL = {
    "stem": (
        "设区域 $D=\\{(x,y):0\\le x\\le 1,\\ 0\\le y\\le x\\}$，"
        "则 $\\displaystyle\\iint_D 2x\\,\\mathrm{d}x\\mathrm{d}y=$（\\quad）。"
    ),
    "choices": {
        "A": "$\\dfrac{1}{3}$",
        "B": "$\\dfrac{2}{3}$",
        "C": "$1$",
        "D": "$\\dfrac{1}{2}$",
    },
    "answer": "B",
}


def replace_question(
    data: dict[str, Any],
    q_id: str,
    *,
    stem: str | None = None,
    choices: dict[str, str] | None = None,
    answer: str | None = None,
) -> dict[str, Any]:
    out = copy.deepcopy(data)
    found = False
    for sec in out.get("sections", []):
        for q in sec.get("questions", []):
            if q.get("id") == q_id:
                if stem is not None:
                    q["stem"] = stem
                if choices is not None:
                    q["choices"] = {**q.get("choices", {}), **choices}
                if answer is not None:
                    q["answer"] = answer
                found = True
                break
        if found:
            break
    if not found:
        raise KeyError(f"question id not found: {q_id}")
    out["_revised"] = q_id
    return out


def revise_from_file(inp: Path, out: Path, q_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    data = load_yaml(inp)
    revised = replace_question(
        data,
        q_id,
        stem=patch.get("stem"),
        choices=patch.get("choices"),
        answer=patch.get("answer"),
    )
    dump_yaml(revised, out)
    return revised
