# -*- coding: utf-8 -*-
"""行内 OMML 写入 .docx（LaTeX → OMML，嵌入 w:r/m:oMath）。

已验证场景：学院 Word 母版含 WPS 公式 OLE 时，docx-mcp replace_text 改不到公式；
docx-mcp add_equation 为段后 m:oMathPara；本模块在同一段落内插入行内公式，Word/WPS 可打开。

依赖：pip install latex2mathml lxml docx-mcp
"""
from __future__ import annotations

import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from latex2mathml.converter import convert
from lxml import etree

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML = "{http://www.w3.org/XML/1998/namespace}"


def mathml_to_omml_nodes(node: etree._Element) -> list[etree._Element]:
    local = etree.QName(node).localname

    if local in ("math", "mrow"):
        res = []
        children = [c for c in node if not callable(c.tag)]
        i = 0
        while i < len(children):
            child = children[i]
            child_local = etree.QName(child).localname
            
            # Check if this child is a sub/sup/subsup containing an integral/summation
            is_nary = False
            base_node = None
            if child_local in ("msub", "msup", "msubsup"):
                child_sub_children = [c for c in child if not callable(c.tag)]
                if len(child_sub_children) >= 1:
                    base_node = child_sub_children[0]
                    base_text = "".join(base_node.itertext()).strip()
                    is_nary = any(
                        c in base_text
                        for c in ("∫", "∬", "∭", "∑", "∏", "\u222b", "\u222c", "\u222d", "\u2211", "\u220f")
                    )
            
            if is_nary:
                # We convert this nary operator and CONSUME all remaining siblings as its integrand/argument!
                nary = etree.Element(f"{M}nary")
                naryPr = etree.SubElement(nary, f"{M}naryPr")
                chr_el = etree.SubElement(naryPr, f"{M}chr")
                chr_el.set(f"{M}val", "".join(base_node.itertext()).strip() or "∫")
                limLoc = etree.SubElement(naryPr, f"{M}limLoc")
                limLoc.set(f"{M}val", "subSup")
                
                sub_el = etree.SubElement(nary, f"{M}sub")
                sup_el = etree.SubElement(nary, f"{M}sup")
                e_el = etree.SubElement(nary, f"{M}e")
                
                child_sub_children = [c for c in child if not callable(c.tag)]
                if child_local == "msub" and len(child_sub_children) >= 2:
                    for x in mathml_to_omml_nodes(child_sub_children[1]):
                        sub_el.append(x)
                elif child_local == "msup" and len(child_sub_children) >= 2:
                    for x in mathml_to_omml_nodes(child_sub_children[1]):
                        sup_el.append(x)
                elif child_local == "msubsup" and len(child_sub_children) >= 3:
                    for x in mathml_to_omml_nodes(child_sub_children[1]):
                        sub_el.append(x)
                    for x in mathml_to_omml_nodes(child_sub_children[2]):
                        sup_el.append(x)
                
                # Consume all remaining siblings of the parent mrow/math into `<m:e>`!
                for sibling in children[i+1:]:
                    for x in mathml_to_omml_nodes(sibling):
                        e_el.append(x)
                
                res.append(nary)
                break
            else:
                res.extend(mathml_to_omml_nodes(child))
                i += 1
        return res

    elif local in ("mi", "mn", "mo", "mtext"):
        r = etree.Element(f"{M}r")
        if local in ("mo", "mn", "mtext"):
            rPr = etree.SubElement(r, f"{M}rPr")
            sty = etree.SubElement(rPr, f"{M}sty")
            sty.set(f"{M}val", "p")
        t = etree.SubElement(r, f"{M}t")
        t.text = node.text or ""
        return [r]

    elif local == "mspace":
        r = etree.Element(f"{M}r")
        t = etree.SubElement(r, f"{M}t")
        t.text = " "
        return [r]

    elif local == "msup":
        children = [c for c in node if not callable(c.tag)]
        if len(children) < 2:
            res = []
            for c in children:
                res.extend(mathml_to_omml_nodes(c))
            return res
        ssup = etree.Element(f"{M}sSup")
        e_el = etree.SubElement(ssup, f"{M}e")
        sup_el = etree.SubElement(ssup, f"{M}sup")
        for x in mathml_to_omml_nodes(children[0]):
            e_el.append(x)
        for x in mathml_to_omml_nodes(children[1]):
            sup_el.append(x)
        return [ssup]

    elif local == "msub":
        children = [c for c in node if not callable(c.tag)]
        if len(children) < 2:
            res = []
            for c in children:
                res.extend(mathml_to_omml_nodes(c))
            return res
        ssub = etree.Element(f"{M}sSub")
        e_el = etree.SubElement(ssub, f"{M}e")
        sub_el = etree.SubElement(ssub, f"{M}sub")
        for x in mathml_to_omml_nodes(children[0]):
            e_el.append(x)
        for x in mathml_to_omml_nodes(children[1]):
            sub_el.append(x)
        return [ssub]

    elif local == "msubsup":
        children = [c for c in node if not callable(c.tag)]
        if len(children) < 3:
            res = []
            for c in children:
                res.extend(mathml_to_omml_nodes(c))
            return res
        base_node = children[0]
        base_text = "".join(base_node.itertext()).strip()
        is_nary = any(
            c in base_text
            for c in ("∫", "∬", "∭", "∑", "∏", "\u222b", "\u222c", "\u222d", "\u2211", "\u220f")
        )
        if is_nary:
            nary = etree.Element(f"{M}nary")
            naryPr = etree.SubElement(nary, f"{M}naryPr")
            chr_el = etree.SubElement(naryPr, f"{M}chr")
            chr_el.set(f"{M}val", base_text or "∫")
            limLoc = etree.SubElement(naryPr, f"{M}limLoc")
            limLoc.set(f"{M}val", "subSup")
            sub_el = etree.SubElement(nary, f"{M}sub")
            sup_el = etree.SubElement(nary, f"{M}sup")
            e_el = etree.SubElement(nary, f"{M}e")
            for x in mathml_to_omml_nodes(children[1]):
                sub_el.append(x)
            for x in mathml_to_omml_nodes(children[2]):
                sup_el.append(x)
            return [nary]
        else:
            ssubsup = etree.Element(f"{M}sSubSup")
            e_el = etree.SubElement(ssubsup, f"{M}e")
            sub_el = etree.SubElement(ssubsup, f"{M}sub")
            sup_el = etree.SubElement(ssubsup, f"{M}sup")
            for x in mathml_to_omml_nodes(children[0]):
                e_el.append(x)
            for x in mathml_to_omml_nodes(children[1]):
                sub_el.append(x)
            for x in mathml_to_omml_nodes(children[2]):
                sup_el.append(x)
            return [ssubsup]

    elif local == "mfrac":
        children = [c for c in node if not callable(c.tag)]
        if len(children) < 2:
            res = []
            for c in children:
                res.extend(mathml_to_omml_nodes(c))
            return res
        f = etree.Element(f"{M}f")
        num = etree.SubElement(f, f"{M}num")
        den = etree.SubElement(f, f"{M}den")
        for x in mathml_to_omml_nodes(children[0]):
            num.append(x)
        for x in mathml_to_omml_nodes(children[1]):
            den.append(x)
        return [f]

    elif local == "msqrt":
        rad = etree.Element(f"{M}rad")
        radPr = etree.SubElement(rad, f"{M}radPr")
        degHide = etree.SubElement(radPr, f"{M}degHide")
        degHide.set(f"{M}val", "1")
        etree.SubElement(rad, f"{M}deg")
        e_el = etree.SubElement(rad, f"{M}e")
        for child in node:
            if callable(child.tag):
                continue
            for x in mathml_to_omml_nodes(child):
                e_el.append(x)
        return [rad]

    elif local == "mroot":
        children = [c for c in node if not callable(c.tag)]
        if len(children) < 2:
            res = []
            for c in children:
                res.extend(mathml_to_omml_nodes(c))
            return res
        rad = etree.Element(f"{M}rad")
        radPr = etree.SubElement(rad, f"{M}radPr")
        deg_el = etree.SubElement(rad, f"{M}deg")
        e_el = etree.SubElement(rad, f"{M}e")
        for x in mathml_to_omml_nodes(children[0]):
            e_el.append(x)
        for x in mathml_to_omml_nodes(children[1]):
            deg_el.append(x)
        return [rad]

    else:
        r = etree.Element(f"{M}r")
        t = etree.SubElement(r, f"{M}t")
        t.text = "".join(node.itertext())
        return [r]


def latex_to_omml_element(latex: str) -> etree._Element:
    mathml = convert(latex)
    tree = etree.fromstring(mathml.encode())
    omath = etree.Element(f"{M}oMath")
    for el in mathml_to_omml_nodes(tree):
        omath.append(el)
    return omath


def text_run(text: str) -> etree._Element:
    r = etree.Element(f"{W}r")
    t = etree.SubElement(r, f"{W}t")
    if text and (text[0].isspace() or text[-1].isspace()):
        t.set(f"{XML}space", "preserve")
    t.text = text
    return r


def omml_run(latex: str) -> etree._Element:
    r = etree.Element(f"{W}r")
    r.append(latex_to_omml_element(latex))
    return r


def rebuild_paragraph(p: etree._Element, segments: list[Segment]) -> None:
    """保留 w:pPr，清空段内 run/OLE，按 text/latex 片段重建。"""
    ppr = p.find(f"{W}pPr")
    for child in list(p):
        if child is not ppr:
            p.remove(child)
    for kind, content in segments:
        if kind == "text":
            p.append(text_run(content))
        elif kind == "latex":
            p.append(omml_run(content))
        else:
            raise ValueError(f"unknown segment kind: {kind!r}")


W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"


def document_paragraphs(root: etree._Element) -> list[etree._Element]:
    """document.xml 内全部 w:p（含表格 cell），与 dump 脚本序号一致。从 1 开始索引。"""
    return list(root.iter(f"{W}p"))


def paragraph_para_id(p: etree._Element) -> str | None:
    pid = p.get(f"{W14}paraId")
    if pid:
        return pid.upper()
    return None


def find_paragraph_by_para_id(root: etree._Element, para_id: str) -> etree._Element:
    want = para_id.strip().upper()
    for p in document_paragraphs(root):
        pid = paragraph_para_id(p)
        if pid == want:
            return p
    raise KeyError(f"para_id {para_id!r} not found in document")


def patch_paragraph_by_index(
    root: etree._Element, index_1based: int, segments: list[Segment]
) -> None:
    """index = document.xml 内 w:p 出现顺序（含表格），从 1 开始。非 w:body 直子段。"""
    paras = document_paragraphs(root)
    if index_1based < 1 or index_1based > len(paras):
        raise IndexError(
            f"paragraph index {index_1based} out of range 1..{len(paras)}"
        )
    rebuild_paragraph(paras[index_1based - 1], segments)


def patch_paragraph_by_para_id(
    root: etree._Element, para_id: str, segments: list[Segment]
) -> None:
    rebuild_paragraph(find_paragraph_by_para_id(root, para_id), segments)


def replace_in_all_text_nodes(root: etree._Element, old: str, new: str) -> int:
    n = 0
    for t in root.iter(f"{W}t"):
        if t.text and old in t.text:
            t.text = t.text.replace(old, new)
            n += 1
    return n


def replace_exam_paper_type(root: etree._Element, paper_type: str = "B") -> int:
    """页眉行「试卷类型」常为拆 run；在含 MATH1027+试卷类型 的段内改独立 A/B run。"""
    for p in document_paragraphs(root):
        texts = [t for t in p.iter(f"{W}t")]
        full = "".join(t.text or "" for t in texts)
        if "试卷类型" not in full or "MATH1027" not in full:
            continue
        for t in texts:
            if t.text and t.text.strip() in ("A", "B"):
                t.text = t.text.replace(t.text.strip(), paper_type)
                return 1
    return 0


def read_document_xml(docx_path: Path) -> tuple[dict[str, bytes], etree._Element]:
    with zipfile.ZipFile(docx_path, "r") as zin:
        parts = {name: zin.read(name) for name in zin.namelist()}
    root = etree.fromstring(parts["word/document.xml"])
    return parts, root


def write_document_xml(docx_path: Path, parts: dict[str, bytes], root: etree._Element) -> None:
    parts["word/document.xml"] = etree.tostring(
        root, encoding="UTF-8", xml_declaration=True, standalone=True
    )
    tmp = docx_path.with_suffix(".inline-omml.tmp.docx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts.items():
            zout.writestr(name, data)
    tmp.replace(docx_path)


def rewrite_docx(src: Path, dst: Path, patch: PatchFn) -> None:
    """复制 src → dst，对 document.xml 执行 patch，写回 zip。"""
    shutil.copy2(src, dst)
    parts, root = read_document_xml(dst)
    patch(root)
    if "word/settings.xml" in parts:
        settings_xml = parts["word/settings.xml"]
        if b"Cambria Math" in settings_xml:
            parts["word/settings.xml"] = settings_xml.replace(b"Cambria Math", b"Times New Roman")
    write_document_xml(dst, parts, root)


def count_inline_omath(root: etree._Element) -> int:
    m = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
    return sum(1 for el in root.iter(f"{m}oMath"))
