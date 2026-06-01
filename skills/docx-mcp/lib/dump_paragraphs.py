#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出 docx 内 w:p 序号、paraId、OLE/OMML、纯文本摘要（改题前校准用）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from inline_omml import (  # noqa: E402
    count_inline_omath,
    document_paragraphs,
    paragraph_para_id,
    read_document_xml,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def para_plain(p) -> str:
    return "".join(t.text or "" for t in p.findall(f".//{W}t"))


def has_ole(p) -> bool:
    return bool(p.findall(f".//{W}object"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("docx", type=Path)
    ap.add_argument("--grep", type=str, default="", help="只显示纯文本含此子串的段")
    ap.add_argument("--ole-only", action="store_true")
    args = ap.parse_args()
    _, root = read_document_xml(args.docx)
    for i, p in enumerate(document_paragraphs(root), 1):
        t = para_plain(p)
        if args.grep and args.grep not in t:
            continue
        if args.ole_only and not has_ole(p):
            continue
        pid = paragraph_para_id(p) or "-"
        flags = []
        if has_ole(p):
            flags.append("OLE")
        om = len(p.findall(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath"))
        if om:
            flags.append(f"OMML×{om}")
        flag = ",".join(flags) or "txt"
        if not t.strip() and not flags:
            continue
        print(f"{i:03d}\t{pid}\t{flag}\t{t[:100]}")
    print(f"# total paragraphs: {len(document_paragraphs(root))}", file=sys.stderr)
    print(f"# inline oMath total: {count_inline_omath(root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
