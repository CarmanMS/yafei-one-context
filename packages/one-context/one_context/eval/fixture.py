"""Overlay layer: apply single-file patches on top of the shared eval fixture.

Stage 2.0.3 refactor (ISS-022): the old whole-subtree overlay (with
`overlay-and-replace` / `strict-new` modes) is removed. Scenarios now point
at a shared fixture via `target_path: features/_evals/<category>/<name>/`
and may optionally declare a small `overlay.apply` list to patch specific
files in the sandbox without forking the fixture.

Each `overlay.apply` item is `{src, dst}`:
  * `src`  — path relative to the scenario directory (must exist).
  * `dst`  — path inside the sandbox; supports `{{ target_path }}`
              interpolation so a patch can target a file *inside* the
              shared fixture without hard-coding the fixture's full path.

Semantics:
  * always `replace` (no mode field).
  * `dst.parent` is `mkdir(parents=True, exist_ok=True)` automatically.
  * each applied file's post-copy sha256 is recorded so the runner can
    write it into `run.json` and the report can verify the actual bytes
    seen by the agent.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from one_context.eval.scenario_config import OverlayConfig


_TARGET_PATH_TOKEN = re.compile(r"\{\{\s*target_path\s*\}\}")


@dataclass(frozen=True)
class OverlayApplied:
    src: Path        # relative-to-scenario src value as declared in YAML
    dst: Path        # absolute path inside the sandbox where bytes landed
    sha256: str      # post-copy sha256 of dst contents


def _interpolate(template: str, target_path: str) -> str:
    """Replace `{{ target_path }}` (any whitespace) with target_path verbatim."""
    return _TARGET_PATH_TOKEN.sub(target_path, template)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_overlay(
    sandbox_root: Path,
    target_path: str,
    overlay: "OverlayConfig | None",
    scenario_dir: Path,
) -> list[OverlayApplied]:
    """Apply single-file patches onto the prepared sandbox.

    Args:
        sandbox_root: prepared sandbox dir (`Sandbox.path`); patches are
            written into this root.
        target_path: scenario's `target_path` value (e.g.
            `"features/_evals/.../"`) — used purely for `{{ target_path }}`
            interpolation in each item's `dst`.
        overlay: parsed `OverlayConfig` (or None / empty `apply` list).
        scenario_dir: scenario YAML's directory; each `item.src` is resolved
            relative to this.

    Returns:
        ordered list of `OverlayApplied`; empty when overlay is None or has
        no `apply` entries.

    Raises:
        FileNotFoundError: when any `item.src` resolved against
            `scenario_dir` does not exist.
        ValueError: when an interpolated `dst` escapes `sandbox_root`.
    """
    if overlay is None or not overlay.apply:
        return []

    sandbox_root = sandbox_root.resolve()
    applied: list[OverlayApplied] = []

    for item in overlay.apply:
        src_abs = (scenario_dir / item.src).resolve()
        if not src_abs.is_file():
            raise FileNotFoundError(
                f"overlay src missing or not a file: {src_abs} "
                f"(declared as {item.src!r} relative to {scenario_dir})"
            )

        dst_rel = _interpolate(item.dst, target_path)
        dst_abs = (sandbox_root / dst_rel).resolve()
        if not str(dst_abs).startswith(str(sandbox_root)):
            raise ValueError(
                f"overlay dst escapes sandbox: {dst_abs} (dst={item.dst!r})"
            )

        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_abs, dst_abs)
        applied.append(OverlayApplied(
            src=Path(item.src),
            dst=dst_abs,
            sha256=_sha256_of(dst_abs),
        ))

    return applied
