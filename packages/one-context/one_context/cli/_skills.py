"""Project skill discovery."""

from __future__ import annotations

import argparse
from pathlib import Path


def _cmd_skills_list(root: Path, _args: argparse.Namespace) -> int:
    from one_context.skills import discover_skills

    skills = discover_skills(root)
    if not skills:
        print("(no project skills)")
        return 0
    for skill in skills:
        print(f"{skill.dir_name}\t{skill.name}\t{skill.source_path}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p_skills = sub.add_parser("skills", help="Project skill commands")
    skills_sub = p_skills.add_subparsers(dest="skills_command", required=True)
    p_list = skills_sub.add_parser("list", help="List skills discovered under skills/")
    p_list.set_defaults(func=_cmd_skills_list)
