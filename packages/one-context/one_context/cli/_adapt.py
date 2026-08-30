"""Adapter generation."""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path, PureWindowsPath

from one_context.agents import load_agents
from one_context.context import build_workspace_context
from one_context.errors import ManifestError
from one_context.profiles import load_mixins, load_profiles, resolve_profile
from one_context.workspaces import load_workspaces


# ── helpers (formerly module-private in cli.py) ──────────────────────────

def _print_dry_run_block(rel_path: str, description: str, body: str) -> None:
    """Print generated content in dry-run mode.

    On Windows, ``sys.stdout`` may use a legacy encoding (e.g. GBK) that
    cannot encode some UTF-8 characters from knowledge files; fall back to
    writing UTF-8 bytes so ``--dry-run`` does not crash.
    """
    block = f"--- {rel_path} ({description}) ---\n{body}\n"
    try:
        sys.stdout.write(block)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(block.encode("utf-8", errors="replace"))


def _generated_target(root: Path, rel_path: str) -> Path:
    """Resolve one generated path without allowing traversal or symlink escape."""
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ManifestError(f"unsafe generated path: {rel_path!r}")
    rel = Path(rel_path)
    if (
        rel == Path(".")
        or rel.is_absolute()
        or PureWindowsPath(rel_path).drive
        or ".." in rel.parts
    ):
        raise ManifestError(f"unsafe generated path: {rel_path!r}")

    root_resolved = root.resolve()
    cursor = root_resolved
    for part in rel.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ManifestError(f"generated path crosses a symlink: {rel_path!r}")
    target = (root_resolved / rel).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ManifestError(f"unsafe generated path: {rel_path!r}") from exc
    return target


def _emit_file(root: Path, gf, dry_run: bool) -> bool:
    """Write a generated file, skipping only byte-identical content."""
    target = _generated_target(root, gf.rel_path)

    if dry_run:
        _print_dry_run_block(gf.rel_path, gf.description, gf.content)
    else:
        if target.is_file() and target.read_text(encoding="utf-8") == gf.content:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(gf.content, encoding="utf-8")
        print(f"wrote: {gf.rel_path} ({gf.description})")

    return True


def _check_generated(root: Path, files: list) -> int:
    """Compare generated content to disk. Return 0 if all match, 1 if any differ."""
    mismatched: list[str] = []
    for gf in files:
        target = _generated_target(root, gf.rel_path)
        if not target.is_file():
            mismatched.append(f"  missing: {gf.rel_path}")
            continue
        existing = target.read_text(encoding="utf-8")
        if existing != gf.content:
            mismatched.append(f"  stale:   {gf.rel_path}")

    if mismatched:
        print("adapt --check: generated files are NOT up-to-date:", file=sys.stderr)
        for line in mismatched:
            print(line, file=sys.stderr)
        print(f"\nRun `onecxt adapt --all` to regenerate.", file=sys.stderr)
        return 1

    print("adapt --check: all generated files are up-to-date.")
    return 0


def _report_dirty_files(root: Path, files: list) -> None:
    """Detect and report files that were modified externally since last adapt."""
    dirty_count = 0
    for gf in files:
        target = _generated_target(root, gf.rel_path)
        if not target.is_file():
            continue
        existing = target.read_text(encoding="utf-8")
        if existing != gf.content:
            dirty_count += 1
            diff_lines = list(difflib.unified_diff(
                existing.splitlines(keepends=True),
                gf.content.splitlines(keepends=True),
                fromfile=f"disk:{gf.rel_path}",
                tofile=f"generated:{gf.rel_path}",
                n=1,
            ))
            add_count = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            del_count = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            print(f"  dirty: {gf.rel_path} (+{add_count}/-{del_count} lines)")

    if dirty_count:
        print(f"warning: {dirty_count} generated file(s) differ from expected output; overwriting.")


# ── command handlers ────────────────────────────────────────────────────

def _cmd_adapt(root: Path, args: argparse.Namespace) -> int:
    # Lazy import to avoid circular deps and keep startup fast
    from one_context.adapters import ADAPTERS, get_adapter, list_adapters
    # Trigger adapter registration via side-effect imports
    import one_context.adapters.claude_code  # noqa: F401
    import one_context.adapters.cursor  # noqa: F401
    import one_context.adapters.hermes  # noqa: F401
    import one_context.adapters.openclaw  # noqa: F401

    workspace_ids: list[str]
    if args.all:
        ws_list, _ = load_workspaces(root)
        workspace_ids = [w["id"] for w in ws_list]
    else:
        if not args.workspace_id:
            print("error: specify a WORKSPACE_ID or use --all", file=sys.stderr)
            return 2
        workspace_ids = [args.workspace_id]

    only = args.only
    if only and only not in ADAPTERS:
        print(
            f"error: unknown adapter {only!r}. "
            f"Available: {', '.join(list_adapters())}",
            file=sys.stderr,
        )
        return 2

    adapter_names = [only] if only else list_adapters()
    dry_run = args.dry_run
    check_mode = getattr(args, "check", False)

    if dry_run and check_mode:
        print("error: --dry-run and --check are mutually exclusive", file=sys.stderr)
        return 2

    agents, _ = load_agents(root)
    _, profiles_by_id = load_profiles(root)

    _, mixins_by_id = load_mixins(root)
    resolved_profiles = {
        pid: resolve_profile(pid, profiles_by_id, mixins_by_id)
        for pid in profiles_by_id
    }

    from one_context.adapters import GeneratedFile
    all_generated: list[GeneratedFile] = []

    for ws_id in workspace_ids:
        try:
            ctx = build_workspace_context(root, ws_id)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

        workspace = ctx["workspace"]
        for aname in adapter_names:
            adapter = get_adapter(aname)
            all_generated.extend(adapter.generate(root, workspace, ctx))

    for aname in adapter_names:
        adapter = get_adapter(aname)
        if agents:
            all_generated.extend(adapter.generate_agents(root, agents, resolved_profiles))

    from one_context.skills import discover_skills
    discovered_skills = discover_skills(root)
    if discovered_skills:
        for aname in adapter_names:
            adapter = get_adapter(aname)
            all_generated.extend(adapter.generate_skills(root, discovered_skills))

    for aname in adapter_names:
        adapter = get_adapter(aname)
        all_generated.extend(adapter.generate_project_artifacts(root, workspace_ids, agents))

    paths = [gf.rel_path for gf in all_generated]
    if len(paths) != len(set(paths)):
        raise ManifestError("multiple adapters produced the same output path")

    if check_mode:
        return _check_generated(root, all_generated)

    _report_dirty_files(root, all_generated)
    written = 0
    skipped = 0
    for gf in all_generated:
        did_write = _emit_file(root, gf, dry_run)
        if did_write:
            written += 1
        else:
            skipped += 1

    if not dry_run and skipped:
        print(f"unchanged: {skipped}; written: {written}")

    return 0


# ── subparser registration ──────────────────────────────────────────────

def register(sub: argparse._SubParsersAction) -> None:
    p_adapt = sub.add_parser(
        "adapt",
        help="Generate tool-specific config files from workspace + profile",
    )
    p_adapt.add_argument(
        "workspace_id",
        nargs="?",
        metavar="WORKSPACE_ID",
        default=None,
        help="Workspace id to generate configs for",
    )
    p_adapt.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Generate configs for all workspaces",
    )
    p_adapt.add_argument(
        "--only",
        metavar="ADAPTER",
        default=None,
        help="Only run a specific adapter (e.g. cursor, claude_code, hermes, openclaw)",
    )
    p_adapt.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print generated content without writing files",
    )
    p_adapt.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Check that generated files are up-to-date (exit 1 if not). Does not write.",
    )
    p_adapt.set_defaults(func=_cmd_adapt)
