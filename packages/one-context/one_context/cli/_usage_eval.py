"""CLI 装配：`onecxt usage-eval daemon-spawn / trend / inspect`。

评审 A-01（P0）：装配代码放 ``cli/_usage_eval.py``（与 ``cli/_eval.py`` 等子模块平级），
业务逻辑（evaluate_session / render_trend）仍在 ``one_context.usage_eval.*``。

主入口 ``register(sub)`` 由 ``cli/__init__.py:build_parser`` 调用一次。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path


def _load_api_env_from_settings(path: Path | None) -> dict | None:
    """从 cc settings JSON 的 env block 读 ANTHROPIC_* 注入到 subprocess。

    用 --api-settings ~/.claude/settings.json.backup.* 让 daemon 跟 ccd2 一样
    走 antchat + GLM-5.1，而不依赖 hook 命令行明文写 token。
    """
    if path is None:
        return None
    if not path.exists():
        print(f"[usage-eval] --api-settings path not found: {path}", file=sys.stderr)
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"[usage-eval] --api-settings not valid JSON: {e}", file=sys.stderr)
        return None
    env_block = data.get("env") or {}
    # 只拣 ANTHROPIC_* 避免顺带污染其他 env
    return {k: v for k, v in env_block.items() if k.startswith("ANTHROPIC_")}


def cmd_daemon_spawn(args) -> int:
    """SessionEnd hook 调用：fork daemon 后台评估本会话。

    M-FIX-1：优先从 stdin 读 cc hook JSON payload（含 ``session_id`` +
    ``transcript_path`` + ``cwd``）；``--session-id`` 是手动 fallback。
    """
    from one_context.usage_eval.daemon import double_fork_and_run
    from one_context.usage_eval.orchestrator import evaluate_session

    hook_payload: dict | None = None
    sid: str | None = args.session_id
    cwd_from_payload: str | None = None

    if args.from_stdin:
        raw = sys.stdin.read()
        try:
            hook_payload = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[usage-eval] --from-stdin set but stdin not JSON: {e}", file=sys.stderr)
            return 2
        sid = sid or hook_payload.get("session_id")
        cwd_from_payload = hook_payload.get("cwd")

    if not sid:
        print("[usage-eval] missing session_id (need --from-stdin or --session-id)",
              file=sys.stderr)
        return 2

    repo_root = Path(args.cwd or cwd_from_payload or os.getcwd()).resolve()
    sid_for_log = sid
    api_settings_path = Path(args.api_settings).expanduser() if args.api_settings else None
    api_env = _load_api_env_from_settings(api_settings_path)

    # 临时调试 — 输出 repo_root 来源决定路径解析的关键
    cwd_source = "--cwd" if args.cwd else ("payload.cwd" if cwd_from_payload else "os.getcwd()")
    _resolved_repo_root = str(repo_root)
    _cwd_from_payload_val = cwd_from_payload

    def payload_fn():
        log_path = Path.home() / ".claude/logs/usage-eval" / f"{sid_for_log}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_path),
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        logging.info(
            "daemon start: repo_root=%s (source=%s, payload.cwd=%r)",
            _resolved_repo_root, cwd_source, _cwd_from_payload_val,
        )
        evaluate_session(
            repo_root=repo_root,
            sid=sid_for_log,
            payload=hook_payload,
            judge_model=args.judge_model,
            api_env=api_env,
        )

    return double_fork_and_run(payload_fn)


def cmd_trend(args) -> int:
    """渲染跨 skill 评分 HTML dashboard（M4 待实现）。"""
    print("[usage-eval] trend 尚未实现（M4 todo）", file=sys.stderr)
    return 1


def cmd_inspect(args) -> int:
    """查看某 skill / 某 runId 详情（M4 待实现）。"""
    print("[usage-eval] inspect 尚未实现（M4 todo）", file=sys.stderr)
    return 1


def register(sub: argparse._SubParsersAction) -> None:
    """注册 usage-eval 子命令；仿 cli/_eval.py:register 范式。"""
    p = sub.add_parser(
        "usage-eval",
        help="Skill 使用现场评估（SessionEnd hook 触发的自学评估闭环）",
        description=(
            "对仓内 skill 在真实 cc 会话里的使用做现场打分 + markdown 改进建议。\n"
            "见 features/core/skill-self-evolution-loop/spec.md。"
        ),
    )
    ssub = p.add_subparsers(dest="usage_eval_cmd", required=True)

    sp = ssub.add_parser(
        "daemon-spawn",
        help="hook 调用：fork daemon 评估本会话",
        description=(
            "SessionEnd hook 触发；double-fork 后台评估本会话用过的所有仓内 skill。\n"
            "父进程 < 100ms 返回，子进程后台跑（有看门狗超时）。\n"
            "首选 --from-stdin 读 hook JSON（含 transcript_path）；"
            "--session-id 是 fallback。"
        ),
        epilog=(
            "例（hook 调用）：onecxt usage-eval daemon-spawn --from-stdin\n"
            "例（手动调试）：onecxt usage-eval daemon-spawn --session-id <uuid> --cwd <repo>"
        ),
    )
    sp.add_argument(
        "--from-stdin", action="store_true",
        help="从 stdin 读 cc hook JSON payload（含 session_id + transcript_path）",
    )
    sp.add_argument("--session-id", default=None, help="fallback：手动指定 sid")
    sp.add_argument(
        "--cwd", default=None,
        help="仓根（缺省取 stdin payload.cwd 或当前 cwd）",
    )
    sp.add_argument(
        "--judge-model", default="GLM-5.1",
        help="评测模型；默认 GLM-5.1，通过 env ANTHROPIC_MODEL 透传（绕过 cc --model 白名单）",
    )
    sp.add_argument(
        "--api-settings", default=None,
        help="从该 cc settings JSON 的 env block 加载 ANTHROPIC_AUTH_TOKEN/BASE_URL 注入到 LLM subprocess "
             "（例：~/.claude/settings.json.backup.20260529_153816 → antchat 端点）",
    )
    sp.set_defaults(func=cmd_daemon_spawn)

    st = ssub.add_parser(
        "trend",
        help="渲染跨 skill 评分 dashboard（M4）",
        description="扫所有 skills/<name>/__usage_eval/INDEX.md，生成单文件 HTML dashboard。",
    )
    st.add_argument("--skill", default=None)
    st.add_argument("--cwd", default=None)
    st.add_argument("--output", default=None)
    st.set_defaults(func=cmd_trend)

    si = ssub.add_parser(
        "inspect",
        help="查看某 skill / 某 runId 详情（M4）",
    )
    si.add_argument("skill")
    si.add_argument("--run-id", default=None)
    si.add_argument("--cwd", default=None)
    si.set_defaults(func=cmd_inspect)
