#!/usr/bin/env python3
"""YAML → PDF（委托 skills/pdf-exam-pipeline）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "skills" / "pdf-exam-pipeline"))

from lib.build_paper import build_pdf, render_tex  # noqa: E402
from lib.yaml_io import load_yaml  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="output/paper.pdf")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--skip-verify", action="store_true")
    args = ap.parse_args()

    pilot = Path(__file__).resolve().parent
    inp = pilot / args.input if not Path(args.input).is_absolute() else Path(args.input)
    out_pdf = pilot / args.out if not Path(args.out).is_absolute() else Path(args.out)
    data = load_yaml(inp)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    if args.no_pdf:
        tex_path = out_pdf.parent / "paper.tex"
        render_tex(data, tex_path)
        print(f"Wrote {tex_path}")
        return 0

    build_pdf(data, out_pdf, yaml_path=inp, skip_verify=args.skip_verify)
    print(f"Wrote {out_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
