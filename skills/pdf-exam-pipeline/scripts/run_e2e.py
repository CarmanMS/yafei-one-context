#!/usr/bin/env python3
"""端到端：MinerU MD → YAML →（可选改题）→ PDF → 验证。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.build_paper import build_pdf  # noqa: E402
from lib.parse_md import find_md, write_parsed_md  # noqa: E402
from lib.revise_question import Q1_DOUBLE_INTEGRAL, replace_question  # noqa: E402
from lib.yaml_io import dump_yaml, load_yaml  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="pdf-exam-pipeline e2e")
    ap.add_argument("--md", required=True, help="MinerU *.md path or glob")
    ap.add_argument("--yaml", default="output/questions.yaml")
    ap.add_argument("--out", default="output/paper.pdf")
    ap.add_argument("--revise-q1", action="store_true", help="replace q1 with built-in new question")
    ap.add_argument("--skip-verify", action="store_true")
    args = ap.parse_args()

    work = Path(__file__).resolve().parent
    md_path = find_md(args.md if Path(args.md).is_absolute() else work / args.md)
    yaml_path = work / args.yaml
    out_pdf = work / args.out

    data = write_parsed_md(md_path, yaml_path)
    print(f"PARSE OK  questions={len(data['sections'][0]['questions'])}  -> {yaml_path}")

    if args.revise_q1:
        data = replace_question(data, "q1", **Q1_DOUBLE_INTEGRAL)
        dump_yaml(data, yaml_path)
        print("REVISE OK  q1 replaced")

    build_pdf(data, out_pdf, yaml_path=yaml_path, skip_verify=args.skip_verify)
    print(f"BUILD OK  -> {out_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
