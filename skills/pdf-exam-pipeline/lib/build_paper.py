"""YAML → LaTeX → PDF。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .verify import verify_all


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def render_tex(data: dict, out_tex: Path, template_name: str = "exam-zh.tex.j2") -> None:
    env = Environment(
        loader=FileSystemLoader(str(skill_root() / "templates")),
        autoescape=select_autoescape(enabled_extensions=()),
    )
    tpl = env.get_template(template_name)
    out_tex.write_text(tpl.render(meta=data["meta"], sections=data["sections"]), encoding="utf-8")


def run_xelatex(work_dir: Path, stem: str = "paper", timeout_sec: int = 180) -> None:
    cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", f"{stem}.tex"]
    env = {**os.environ, "MIKTEX_ENABLE_INSTALLER": "1"}
    for _ in range(2):
        r = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            env=env,
        )
        if r.returncode != 0:
            tail = (r.stdout or "")[-4000:] + (r.stderr or "")[-4000:]
            raise RuntimeError(f"xelatex failed:\n{tail}")


def build_pdf(data: dict, out_pdf: Path, yaml_path: Path | None = None, skip_verify: bool = False) -> Path:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    tex_path = out_pdf.parent / "paper.tex"
    render_tex(data, tex_path)
    if not shutil.which("xelatex"):
        raise RuntimeError("xelatex not found — install MiKTeX or TeX Live")
    run_xelatex(out_pdf.parent, "paper")
    built = out_pdf.parent / "paper.pdf"
    if built != out_pdf:
        try:
            shutil.copy2(built, out_pdf)
        except PermissionError:
            alt = out_pdf.with_stem(out_pdf.stem + "-new")
            shutil.copy2(built, alt)
            raise RuntimeError(f"cannot write {out_pdf} (file locked?); wrote {alt}") from None
    if not skip_verify:
        errors = verify_all(tex_path, out_pdf, yaml_path)
        if errors:
            raise RuntimeError("VERIFY FAIL:\n  " + "\n  ".join(errors))
    return out_pdf
