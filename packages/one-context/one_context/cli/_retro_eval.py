"""CLI 装配：`onecxt retro-eval scan / list`。

业务逻辑在 ``one_context.retro_eval.*``；本文件只做 argparse 装配 + 输出。
仿 cli/_usage_eval.py：handler 只收 ``args``，不依赖 one-context root 强制校验
（要能从任意用户仓发起回溯分析）。signature 需要 repo_root，故提供 --repo-root，
缺省时尝试 find_root()，再失败则跳过 signature（仅强信号判定）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _resolve_repo_root(args) -> Path:
    """解析 one-context 仓根用于定位 signature；失败则回退当前 cwd。"""
    if getattr(args, "repo_root", None):
        return Path(args.repo_root).expanduser().resolve()
    try:
        from one_context.root import find_root
        return find_root()
    except Exception:  # noqa: BLE001 — 任意仓调用时找不到 root 属正常
        return Path(os.getcwd())


def cmd_scan(args) -> int:
    from one_context.retro_eval import scan

    repo_root = _resolve_repo_root(args)
    result = scan(
        args.skill,
        repo_root=repo_root,
        scope=args.scope,
        cwd=Path(args.cwd).resolve() if args.cwd else None,
        since_days=args.since_days,
        max_sessions=args.max_sessions,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 0


def cmd_diagnose(args) -> int:
    """串 scan → aggregate → divergence，输出确定性诊断证据包（JSON）。

    本命令只做确定性层；LLM 综合诊断与改进 patch 由 SKILL.md 主线接手。
    """
    from one_context.retro_eval import aggregate, check_divergence, scan

    repo_root = _resolve_repo_root(args)
    scan_result = scan(
        args.skill,
        repo_root=repo_root,
        scope=args.scope,
        cwd=Path(args.cwd).resolve() if args.cwd else None,
        since_days=args.since_days,
        max_sessions=args.max_sessions,
    )
    agg = aggregate(scan_result)

    # 定位被诊断 skill 的 SKILL.md 做分叉检测
    skill_md_path = repo_root / "skills" / args.skill / "SKILL.md"
    divergence: dict | None = None
    if skill_md_path.is_file():
        divergence = check_divergence(skill_md_path.read_text(), scan_result)
    else:
        print(f"[retro-eval] 未找到 {skill_md_path}，跳过分叉检测", file=sys.stderr)

    bundle = {
        "skill": args.skill,
        "scan": scan_result,
        "aggregate": agg,
        "divergence": divergence,
    }
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


def _print_human(r: dict) -> None:
    print(f"skill: {r['skill']}  (scope={r['scope']}, signature={'yes' if r['signature_present'] else 'no'})")
    print(f"扫描 session: {r['sessions_scanned']}  →  真实执行: {r['real_execution_count']}")
    if r["errors"]:
        print(f"⚠️  {len(r['errors'])} 个文件解析失败", file=sys.stderr)
    print()
    for t in r["real_executions"]:
        chain = " → ".join(t["tool_chain"][:8]) + (" …" if len(t["tool_chain"]) > 8 else "")
        print(f"  [{t['verdict']:6}] {t['short']}  | {'; '.join(t['evidence'])}")
        if chain:
            print(f"           chain: {chain}")


def cmd_list(args) -> int:
    """列出本机会话语料里出现过的 skill + 粗略提及计数（不做真实执行判定）。"""
    from one_context.retro_eval.scan import detect_session_roots, project_dir_name

    roots = detect_session_roots()
    if not roots:
        print("[retro-eval] 未发现 cc 会话根目录", file=sys.stderr)
        return 1
    cwd = Path(args.cwd).resolve() if args.cwd else Path(os.getcwd())
    dirs = []
    if args.scope == "current-project":
        name = project_dir_name(cwd)
        dirs = [r / name for r in roots if (r / name).is_dir()]
    else:
        dirs = roots
    files = [f for d in dirs for f in d.glob("*.jsonl")]
    print(f"会话语料：{len(files)} 个 jsonl（scope={args.scope}）")
    print("提示：用 `onecxt retro-eval scan <skill>` 对具体 skill 做真实执行判定。")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "retro-eval",
        help="Skill 跨会话回溯诊断（从历史会话语料聚合单个 skill 的真实执行轨迹）",
        description=(
            "扫本机 cc 会话语料，区分某 skill 的「真实执行」与「仅文本提及」，\n"
            "为回溯进化诊断提供确定性检索层。\n"
            "见 features/core/skill-retrospective-evolution/tech_design.md。"
        ),
    )
    ssub = p.add_subparsers(dest="retro_eval_cmd", required=True)

    sp = ssub.add_parser(
        "scan",
        help="检索某 skill 的真实执行 session（48 提及 → N 真实执行）",
        epilog="例：onecxt retro-eval scan info-radar --json",
    )
    _add_query_args(sp)
    sp.add_argument("--json", action="store_true", help="输出 JSON（供 SKILL.md 编排消费）")
    sp.set_defaults(func=cmd_scan)

    dp = ssub.add_parser(
        "diagnose",
        help="确定性诊断证据包：scan + 失败聚合 + 文档-行为分叉初判（JSON）",
        description=(
            "串 scan → aggregate → divergence，输出确定性证据包供 SKILL.md 主线做 LLM 综合诊断。\n"
            "本命令不调 LLM、不写报告——report.md / patch.md 由 skill 主线生成。"
        ),
        epilog="例：onecxt retro-eval diagnose info-radar > evidence.json",
    )
    _add_query_args(dp)
    dp.set_defaults(func=cmd_diagnose)

    sl = ssub.add_parser("list", help="列出本机会话语料规模")
    sl.add_argument("--scope", choices=["current-project", "all"], default="current-project")
    sl.add_argument("--cwd", default=None)
    sl.set_defaults(func=cmd_list)


def _add_query_args(p: argparse.ArgumentParser) -> None:
    """scan / diagnose 共享的检索参数。"""
    p.add_argument("skill", help="skill 名（对应 skills/<name>/）")
    p.add_argument(
        "--scope", choices=["current-project", "all"], default="current-project",
        help="current-project（默认，仅扫当前 cwd 对应会话，隐私优先）/ all（全部会话）",
    )
    p.add_argument("--cwd", default=None, help="按此 cwd 定位 current-project 会话目录（缺省取当前）")
    p.add_argument("--repo-root", default=None, help="one-context 仓根（定位 .retro-signature.yaml / SKILL.md；缺省自动探测）")
    p.add_argument("--since-days", type=int, default=None, help="仅看最近 N 天的会话")
    p.add_argument("--max-sessions", type=int, default=None, help="最多分析 N 个候选会话")
