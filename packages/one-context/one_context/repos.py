from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlparse

import yaml

from one_context.errors import ManifestError
from one_context.identifiers import is_portable_id


def _repo_name_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = (parsed.path or "").strip("/")
    if not path:
        raise ManifestError(f"Cannot infer repo name from URL: {url}")
    segment = path.split("/")[-1]
    if segment.endswith(".git"):
        segment = segment[:-4]
    if not segment or not re.match(r"^[\w.\-]+$", segment):
        raise ManifestError(f"Invalid repo name segment from URL: {url!r} -> {segment!r}")
    return segment


def _normalize_aliases(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        out: list[str] = []
        for x in raw:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out
    raise ManifestError(f"alias must be string or list of strings, got {type(raw)}")


def load_repos(root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """
    Parse meta/repos.yaml.

    Returns (entries, by_key) where by_key maps casefolded id or alias to entry.
    """
    manifest = root / "meta" / "repos.yaml"
    if not manifest.is_file():
        raise ManifestError(f"Manifest not found: {manifest}")

    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ManifestError("repos.yaml root must be a mapping")

    raw_list = data.get("repos")
    if not isinstance(raw_list, list):
        raise ManifestError("repos.yaml must contain a 'repos' list")

    entries: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}

    for i, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise ManifestError(f"repos[{i}] must be a mapping")

        url = item.get("url")
        if not url or not isinstance(url, str):
            raise ManifestError(f"repos[{i}] needs a string 'url'")

        repo_name = _repo_name_from_url(url)
        category = item.get("category")
        path_str = item.get("path")

        if path_str:
            if not isinstance(path_str, str):
                raise ManifestError(f"repos[{i}].path must be a string")
            rel = Path(path_str)
        else:
            if not category or not isinstance(category, str):
                raise ManifestError(
                    f"repos[{i}] needs 'category' when 'path' is omitted"
                )
            category = category.strip()
            if not is_portable_id(category):
                raise ManifestError(f"repos[{i}].category is not a portable id")
            rel = Path("repos") / category / repo_name

        if (
            rel.is_absolute()
            or PureWindowsPath(str(path_str or rel)).drive
            or not rel.parts
            or ".." in rel.parts
            or rel == Path(".")
        ):
            raise ManifestError(
                f"repos[{i}].path must be a relative path inside the workspace"
            )
        try:
            (root.resolve() / rel).resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise ManifestError(
                f"repos[{i}].path must stay inside the workspace"
            ) from exc

        rid = item.get("id")
        if rid is None:
            rid = repo_name
        elif not isinstance(rid, str) or not rid.strip():
            raise ManifestError(f"repos[{i}].id must be a non-empty string")
        else:
            rid = rid.strip()
        if not is_portable_id(rid):
            raise ManifestError(f"repos[{i}].id is not a portable id: {rid!r}")

        description = item.get("description")
        if description is not None and not isinstance(description, str):
            raise ManifestError(f"repos[{i}].description must be a string")

        aliases = _normalize_aliases(item.get("alias"))
        if "aliases" in item:
            aliases.extend(_normalize_aliases(item["aliases"]))
        for alias in aliases:
            if not is_portable_id(alias):
                raise ManifestError(
                    f"repos[{i}] alias is not a portable id: {alias!r}"
                )

        entry: dict[str, Any] = {
            "id": rid,
            "url": url.strip(),
            "path": rel,
            "description": description or "",
            "aliases": aliases,
        }
        entries.append(entry)

        def register(key: str) -> None:
            k = key.strip()
            if not k:
                return
            lk = k.casefold()
            if lk in by_key and by_key[lk] is not entry:
                raise ManifestError(f"Duplicate id/alias (case-insensitive): {k!r}")
            by_key[lk] = entry

        register(rid)
        for a in aliases:
            register(a)

    return entries, by_key
