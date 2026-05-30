#!/usr/bin/env python3
"""仅改指定题（默认 q1 → 二重积分）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "skills" / "pdf-exam-pipeline"))

from lib.revise_question import Q1_DOUBLE_INTEGRAL, replace_question  # noqa: E402
from lib.yaml_io import dump_yaml, load_yaml  # noqa: E402

PRESETS = {"q1-double-integral": Q1_DOUBLE_INTEGRAL}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--q-id", default="q1")
    ap.add_argument("--preset", default="q1-double-integral", choices=sorted(PRESETS))
    args = ap.parse_args()

    pilot = Path(__file__).resolve().parent
    inp = pilot / args.inp if not Path(args.inp).is_absolute() else Path(args.inp)
    out = pilot / args.out if not Path(args.out).is_absolute() else Path(args.out)
    patch = PRESETS[args.preset]
    data = replace_question(load_yaml(inp), args.q_id, **patch)
    dump_yaml(data, out)
    print(f"Revised {args.q_id} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
