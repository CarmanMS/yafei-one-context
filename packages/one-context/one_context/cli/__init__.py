"""`onecxt` CLI entry point and parser assembly.

Sub-modules each own a coherent slice of the CLI:
    _meta      doctor / sync / repo / workspace / context / profile / agent
    _worktree  worktree setup/status/teardown
    _skills    Claude Code runtime skills list/install/uninstall
    _adapt     adapter generation + git hook install/uninstall
    _eval      skill eval runner

Each sub-module exposes a `register(sub: _SubParsersAction)` function
that registers its subparsers. This file just chains them.

For backwards compat with existing tests that import private handlers
directly (`from one_context.cli import _cmd_adapt`), every public
`_cmd_*` is re-exported below.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from one_context import __version__
from one_context.errors import ManifestError
from one_context.log import setup_logging
from one_context.root import find_root

from one_context.cli import (
    _adapt, _eval, _meta, _recorder, _retro_eval, _skills, _usage_eval, _worktree,
)

# Re-exports for backwards compat with tests:
from one_context.cli._adapt import (  # noqa: F401
    _check_generated,
    _cmd_adapt,
    _cmd_adapt_install,
    _cmd_adapt_uninstall,
    _emit_file,
    _print_dry_run_block,
    _report_dirty_files,
)
from one_context.cli._eval import _cmd_eval_dispatch, _run_many  # noqa: F401
from one_context.cli._meta import (  # noqa: F401
    _cmd_agent_list,
    _cmd_agent_show,
    _cmd_context_export,
    _cmd_doctor,
    _cmd_manifest_list,
    _cmd_profile_list,
    _cmd_profile_show,
    _cmd_repo_list,
    _cmd_sync,
    _cmd_workspace_list,
    _cmd_workspace_show,
)
from one_context.cli._skills import (  # noqa: F401
    _cmd_skills_install,
    _cmd_skills_list,
    _cmd_skills_uninstall,
)
from one_context.cli._worktree import (  # noqa: F401
    _cmd_worktree_setup,
    _cmd_worktree_status,
    _cmd_worktree_teardown,
)

logger = logging.getLogger("one_context.cli")


def _resolve_root(path: Path | None) -> Path:
    if path is not None:
        root = path.expanduser().resolve()
        if not (root / "meta" / "repos.yaml").is_file():
            raise ManifestError(f"Not an one-context root (missing meta/repos.yaml): {root}")
        return root
    return find_root()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="onecxt",
        description="one-context — multi-repository workspace CLI",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="one-context root (directory containing meta/repos.yaml). "
        "Default: walk parents from cwd or use ONECXT_ROOT.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose (DEBUG) logging to stderr",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    _meta.register(sub)
    _adapt.register(sub)
    _worktree.register(sub)
    _skills.register(sub)
    _eval.register(sub)
    _recorder.register(sub)
    _usage_eval.register(sub)
    _retro_eval.register(sub)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # recorder subcommands operate on /tmp/onecxt-recorder/, not the
    # workspace tree — skip root resolution so they work from any cwd.
    if args.command == "recorder":
        raise SystemExit(args.func(Path("."), args))

    # usage-eval is invoked by cc SessionEnd hook from arbitrary user repos
    # (not necessarily one-context). Handlers take only (args), and use
    # --cwd / payload.cwd for repo path.
    if args.command == "usage-eval":
        raise SystemExit(args.func(args))

    # retro-eval is a回溯分析工具，可从任意仓发起；不强制 one-context root。
    if args.command == "retro-eval":
        raise SystemExit(args.func(args))

    try:
        root = _resolve_root(args.root)
    except ManifestError as e:
        print(e.message, file=sys.stderr)
        raise SystemExit(1) from e

    raise SystemExit(args.func(root, args))
