"""Portable manifest identifiers."""

from __future__ import annotations

import re


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_WINDOWS_RESERVED = {
    "aux", "con", "nul", "prn",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def is_portable_id(value: str) -> bool:
    return bool(
        len(value) <= 64
        and _SAFE_ID.fullmatch(value)
        and not value.endswith(".")
        and value.split(".", 1)[0].casefold() not in _WINDOWS_RESERVED
    )
