#!/usr/bin/env python3
"""MinerU MD → YAML（委托 skill lib）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "skills" / "pdf-exam-pipeline"))

from lib.parse_md import find_md, write_parsed_md  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", default="questions/parsed.yaml")
    args = ap.parse_args()
    pilot = Path(__file__).resolve().parent
    md = find_md(args.md if Path(args.md).is_absolute() else pilot / args.md)
    out = pilot / args.out
    data = write_parsed_md(md, out)
    n = len(data["sections"][0]["questions"])
    print(f"Wrote {out} ({n} questions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
