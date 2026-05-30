#!/usr/bin/env python3
"""构建后验证（委托 skill lib）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "skills" / "pdf-exam-pipeline"))

from lib.verify import verify_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default="output/paper.tex")
    ap.add_argument("--pdf", default="output/paper.pdf")
    ap.add_argument("--yaml", default=None)
    args = ap.parse_args()

    pilot = Path(__file__).resolve().parent
    tex = pilot / args.tex if not Path(args.tex).is_absolute() else Path(args.tex)
    pdf = pilot / args.pdf if not Path(args.pdf).is_absolute() else Path(args.pdf)
    yaml_path = None
    if args.yaml:
        yaml_path = pilot / args.yaml if not Path(args.yaml).is_absolute() else Path(args.yaml)

    errors = verify_all(tex, pdf, yaml_path)
    if errors:
        print("VERIFY FAIL")
        for e in errors:
            print(" ", e)
        return 1
    print("VERIFY OK")
    print(f"  tex: {tex}")
    print(f"  pdf: {pdf} ({pdf.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
