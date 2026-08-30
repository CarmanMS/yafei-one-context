from pathlib import Path

import pytest

from one_context.context_sources import resolve_context_source


def test_context_source_boundary(tmp_path: Path):
    rel, target = resolve_context_source(tmp_path, "docs/readme.md")
    assert rel.as_posix() == "docs/readme.md"
    assert target == (tmp_path / "docs" / "readme.md").resolve()

    for raw in ("knowledge/private.md", "Knowledge/private.md", "../private.md"):
        with pytest.raises(ValueError):
            resolve_context_source(tmp_path, raw)
