"""Skill evaluation runner (`onecxt eval ...`)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _run_many(
    root: Path,
    rows: list[tuple[str, str]],
    args: argparse.Namespace,
) -> int:
    """Run a list of `(skill, scenario)` pairs; return non-zero on any FAIL.

    Stage 2.7: when ``--concurrency N > 1`` use a thread pool. APFS
    clonefile sandboxes are COW-isolated, so concurrent runs do not
    contend on disk; the only meaningful upper bound is CPU + Anthropic
    rate-limit. We report results in submission order so logs stay
    deterministic regardless of completion order.
    """
    from concurrent.futures import ThreadPoolExecutor
    from one_context.eval.runner import run as eval_run

    concurrency = max(1, int(getattr(args, "concurrency", 1) or 1))
    keep_tmp = bool(getattr(args, "keep_tmp", False))
    with_diff = bool(getattr(args, "diff", False))

    def _run_one(skill_name: str, scn_name: str):
        tgt = f"{skill_name}/{scn_name}"
        try:
            outcome = eval_run(
                repo_root=root, target=tgt,
                keep_tmp=keep_tmp,
                skill_override=None,
                with_diff=with_diff,
            )
            return tgt, outcome, None
        except Exception as e:  # noqa: BLE001 — surfaced per-scenario
            return tgt, None, e

    any_fail = False
    if concurrency == 1:
        results = [_run_one(s, sc) for s, sc in rows]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_run_one, s, sc) for s, sc in rows]
            results = [f.result() for f in futures]

    for tgt, outcome, err in results:
        if err is not None:
            print(f"ERR \t{tgt}\t{err}", file=sys.stderr)
            any_fail = True
            continue
        tag = "PASS" if outcome.overall == "PASS" else "FAIL"
        if outcome.overall != "PASS":
            any_fail = True
        print(f"{tag}\t{tgt}\trunId={outcome.run_id}")

    return 1 if any_fail else 0


def _cmd_eval_dispatch(root: Path, args: argparse.Namespace) -> int:
    """Dispatch on the `target` positional: keywords vs `<skill>/<scenario>`."""
    target = args.target

    # `--all` is an alias for the `all` keyword (Stage 2.4)
    if getattr(args, "run_all", False) and target != "all":
        target = "all"

    if target == "list":
        from one_context.eval.runner import list_scenarios
        rows = list_scenarios(root)
        if not rows:
            print("(no scenarios — add skills/<name>/evals/<scenario>/scenario.yaml)")
            return 0
        for skill, scn in rows:
            print(f"{skill}/{scn}")
        return 0

    if target == "clean":
        from one_context.eval import sandbox as sb
        from one_context.eval.runner import clean_reports
        orphans = sb.clean_orphans()
        for p in orphans:
            print(f"removed tmp: {p}")
        if not args.tmp_only:
            n = clean_reports(root)
            print(f"removed __reports/ from {n} scenario(s)")
        return 0

    if target == "runs":
        sub = getattr(args, "judge_test_target", None)
        if not sub or "/" not in sub:
            print(
                "error: `runs` requires <skill>/<scenario> argument",
                file=sys.stderr,
            )
            return 2
        skill_name, scn_name = sub.split("/", 1)
        scn_dir = root / "skills" / skill_name / "evals" / scn_name
        if not scn_dir.is_dir():
            print(f"error: scenario dir missing: {scn_dir}", file=sys.stderr)
            return 2
        from one_context.eval.runs_index import render_runs_index
        out = render_runs_index(
            scenario_dir=scn_dir, skill=skill_name, scenario=scn_name,
        )
        print(f"runs index: {out}")
        return 0

    if target == "judge-test":
        sub = getattr(args, "judge_test_target", None)
        if not sub:
            print(
                "error: judge-test requires a <skill>/<scenario> argument",
                file=sys.stderr,
            )
            return 2
        from one_context.eval.judge_test import run_judge_test
        try:
            _, matched, total = run_judge_test(repo_root=root, target=sub)
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        except Exception as e:  # noqa: BLE001
            print(f"error: {e}", file=sys.stderr)
            return 2
        if total >= 4:
            return 0 if matched >= 3 else 1
        return 0 if matched == total else 1

    if target == "init":
        sub = getattr(args, "judge_test_target", None)
        if not sub or "/" not in sub:
            print(
                "error: `init` requires <skill>/<scenario> argument",
                file=sys.stderr,
            )
            return 2
        skill_name, scn_name = sub.split("/", 1)
        from one_context.eval.scaffold import init_scenario, InitError
        try:
            out = init_scenario(repo_root=root, skill=skill_name, scenario=scn_name)
        except InitError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"init OK\t{sub}\t{out.scenario_dir}")
        for p in out.files_created:
            print(f"  created: {p.relative_to(root)}")
        for w in out.warnings:
            print(f"  warning: {w}", file=sys.stderr)
        return 0

    if target == "all":
        from one_context.eval.runner import list_scenarios
        rows = list_scenarios(root)
        if not rows:
            print("(no scenarios)")
            return 0
        return _run_many(root, rows, args)

    if getattr(args, "judge_test_target", None) == "snapshot":
        if "/" not in target:
            print(
                "error: `snapshot` requires <skill>/<scenario> before it",
                file=sys.stderr,
            )
            return 2
        skill_name, scn_name = target.split("/", 1)
        scn_dir = root / "skills" / skill_name / "evals" / scn_name
        if not scn_dir.is_dir():
            print(f"error: scenario dir missing: {scn_dir}", file=sys.stderr)
            return 2
        reason = getattr(args, "reason", None)
        if not reason:
            print(
                "error: snapshot requires --reason \"<text>\"",
                file=sys.stderr,
            )
            return 2
        from one_context.eval.baseline import snapshot as bl_snapshot, SnapshotError
        try:
            out = bl_snapshot(
                scenario_dir=scn_dir,
                reason=reason,
                source_run_id=getattr(args, "run_id", None),
            )
        except SnapshotError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        except (FileNotFoundError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"snapshot OK\t{target}\trunId={out.source_run_id}")
        print(f"  baseline: {out.baseline_dir}")
        print(f"  metadata: {out.baseline_json_path}")
        return 0

    if "/" not in target:
        from one_context.eval.runner import list_scenarios
        rows = [(s, sc) for s, sc in list_scenarios(root) if s == target]
        if not rows:
            print(
                f"error: no scenarios under skill {target!r}",
                file=sys.stderr,
            )
            return 2
        return _run_many(root, rows, args)

    # Otherwise: `<skill>/<scenario>`
    from one_context.eval.runner import run as eval_run

    skill_override = (
        Path(args.skill_override).expanduser().resolve()
        if args.skill_override else None
    )
    try:
        outcome = eval_run(
            repo_root=root,
            target=target,
            keep_tmp=args.keep_tmp,
            skill_override=skill_override,
            with_diff=getattr(args, "diff", False),
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    pass_str = "PASS" if outcome.overall == "PASS" else "FAIL"
    print(f"{pass_str}\t{target}\trunId={outcome.run_id}")
    print(f"  report: {outcome.report_html_path}")
    print(f"  json:   {outcome.run_json_path}")
    if outcome.kept_sandbox:
        print(f"  sandbox kept at: {outcome.sandbox_path}")
    return 0 if outcome.overall == "PASS" else 1


def register(sub: argparse._SubParsersAction) -> None:
    # Eval — run skill evaluations.
    # `target` accepts either a special keyword (list / clean) OR a
    # `<skill>/<scenario>` string (positional). We dispatch in the handler.
    p_eval = sub.add_parser(
        "eval",
        help="Run skill evaluations (LLM rubric). "
        "Usage: onecxt eval <skill>/<scenario> | list | clean | "
        "judge-test <skill>/<scenario> | runs <skill>/<scenario>. "
        "PASS rolls __reports/: only the latest run survives; FAIL accumulates "
        "until the next PASS sweeps it.",
    )
    p_eval.add_argument(
        "target", metavar="TARGET",
        help="<skill>/<scenario>, or 'list' / 'clean' / 'judge-test'",
    )
    p_eval.add_argument(
        "judge_test_target",
        nargs="?",
        default=None,
        metavar="SKILL/SCENARIO",
        help="(only with `judge-test`) <skill>/<scenario> whose "
        "ground_truth/*.yaml feeds the judge calibration loop",
    )
    p_eval.add_argument(
        "--keep-tmp", action="store_true", default=False,
        help="Keep the sandbox /tmp/onecxt-eval-<runId>/ for debugging",
    )
    p_eval.add_argument(
        "--skill-override", default=None, metavar="DIR",
        help="(Phase 2) replace skills/<skill>/{SKILL.md, references, assets, scripts} with files from DIR",
    )
    p_eval.add_argument(
        "--tmp-only", action="store_true", default=False,
        help="(with `clean`) only clean /tmp; keep __reports/. Note: `clean` "
        "wipes __reports/ wholesale across all scenarios; the per-run PASS "
        "rolling only prunes older runIds inside the current scenario.",
    )
    p_eval.add_argument(
        "--reason", default=None, metavar="TEXT",
        help="(with `snapshot`) human-readable reason for this baseline",
    )
    p_eval.add_argument(
        "--run-id", default=None, metavar="RUNID",
        help="(with `snapshot`) pin source run; default = latest",
    )
    p_eval.add_argument(
        "--diff", action="store_true", default=False,
        help="(Stage 2.2) after the run, diff against __baselines/baseline.json"
        " and render a Diff tab in the HTML report",
    )
    p_eval.add_argument(
        "--all", dest="run_all", action="store_true", default=False,
        help="(Stage 2.4) run every scenario; equivalent to `eval all`",
    )
    p_eval.add_argument(
        "--concurrency", type=int, default=1, metavar="N",
        help="(Stage 2.7) run up to N scenarios in parallel (only meaningful "
        "with `eval all` / `eval <skill>`); APFS clonefile sandboxes are "
        "COW-isolated so N>1 is safe.",
    )
    p_eval.set_defaults(func=_cmd_eval_dispatch)
