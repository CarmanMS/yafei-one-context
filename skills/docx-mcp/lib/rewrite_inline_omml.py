#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI：对 .docx 应用 JSON 段落补丁（行内 OMML）。

补丁 JSON 格式见 skills/docx-mcp/references/inline-omml-patches.example.json

示例：
  python skills/docx-mcp/lib/rewrite_inline_omml.py \\
    --src paper-A.docx --dst paper-B-pilot.docx \\
    --patches patches.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 允许从仓库根直接运行
_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from inline_omml import (  # noqa: E402
    patch_paragraph_by_index,
    patch_paragraph_by_para_id,
    replace_exam_paper_type,
    replace_in_all_text_nodes,
    rewrite_docx,
)


def load_patches(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("patches file must be a JSON object")
    return data


def apply_json_patch(root, spec: dict) -> None:
    if spec.get("exam_paper_type"):
        replace_exam_paper_type(root, str(spec["exam_paper_type"]))
    for item in spec.get("text_replace", []):
        replace_in_all_text_nodes(root, item["old"], item["new"])
    for item in spec.get("paragraphs", []):
        segments = [(s["kind"], s["content"]) for s in item["segments"]]
        if "para_id" in item:
            patch_paragraph_by_para_id(root, item["para_id"], segments)
        elif "index" in item:
            patch_paragraph_by_index(root, int(item["index"]), segments)
        else:
            raise ValueError("paragraph patch requires para_id or index")


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply inline OMML paragraph patches to a docx")
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--dst", type=Path, required=True)
    ap.add_argument("--patches", type=Path, required=True)
    args = ap.parse_args()
    if not args.src.is_file():
        print(f"ERROR: missing {args.src}", file=sys.stderr)
        return 1
    spec = load_patches(args.patches)

    def patch(root):
        apply_json_patch(root, spec)

    rewrite_docx(args.src, args.dst, patch)
    print(f"OK -> {args.dst}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
