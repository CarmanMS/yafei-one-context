"""YAML 读写：保留 LaTeX 多行块。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _repr_str(dumper: yaml.Dumper, data: str) -> yaml.nodes.ScalarNode:
    if "\n" in data or "$" in data or "\\" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, _repr_str)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
