"""Orchestrate one full eval run.

Flow (tech_design.md §2.1):
  1. sandbox.prepare    — mkdir + git archive
  2. fixture.overlay    — copy `<scenario>/fixture/*` into sandbox
  3. artifacts.snapshot (pre)  — sha256 every whitelist match
  4. provider.run_provider     — spawn `claude -p` via the JS provider
  5. artifacts.snapshot (post) — sha256 again
  6. artifacts.diff + copy_into_report
  7. judge.evaluate            — LLM rubric judge (cheap haiku)
  8. report.write_run_json + report.render
  9. sandbox.teardown
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from one_context.eval import artifacts as art_mod
from one_context.eval import assertions as assertions_mod
from one_context.eval import diff as diff_mod
from one_context.eval import events as events_mod
from one_context.eval import fixture as fix_mod
from one_context.eval import sandbox as sb_mod
from one_context.eval import judge as judge_mod
from one_context.eval import provider as provider_mod
from one_context.eval import report as report_mod
from one_context.eval import session_inject as si_mod
from one_context.eval.scenario_config import ScenarioConfig, load_scenario
from one_context.eval.skill_config import SkillEvalConfig, load_skill_eval

logger = logging.getLogger("one_context.eval.runner")

# R-5 治理 B (design §16.7.5): cc-builtin external tools that the
# replay model commonly escapes to when the mock-named tool is denied.
# Auto-added to the disallow list when not already present, so the
# replay can only use mocked tools or cc-local tools (Read/Edit/...).
# Bash is intentionally omitted — too commonly mocked, and the rare
# scenario that records no Bash but wants it live during replay would
# break. WebSearch/WebFetch are the observed escape paths in real
# runs (see design §16.7.3).
CC_BUILTIN_EXTERNAL_TOOLS_TO_BAN: tuple[str, ...] = ("WebSearch", "WebFetch")


def _resolve_skill_and_scenario(
    repo_root: Path, target: str
) -> tuple[str, str, Path, Path, SkillEvalConfig, ScenarioConfig]:
    """Parse `<skill>/<scenario>` and load both configs from disk."""
    if "/" not in target:
        raise ValueError(
            f"expected '<skill>/<scenario>', got: {target!r}"
        )
    skill, scenario = target.split("/", 1)
    if not skill or not scenario or "/" in scenario:
        raise ValueError(f"invalid skill/scenario: {target!r}")

    skill_dir = repo_root / "skills" / skill
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"skill dir missing: {skill_dir}")
    scenario_dir = skill_dir / "evals" / scenario
    if not scenario_dir.is_dir():
        raise FileNotFoundError(f"scenario dir missing: {scenario_dir}")

    skill_cfg = load_skill_eval(skill_dir)
    scen_cfg = load_scenario(scenario_dir)
    return skill, scenario, skill_dir, scenario_dir, skill_cfg, scen_cfg


def _file_sha256(path: Path) -> str:
    """R-10a helper: stable sha256 for baseline artifact cache_key."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _read_head(path: Path, max_bytes: int = 4096) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except OSError:
        return ""


def _git_user_email(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "config", "--get", "user.email"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _copy_overlay_files(
    *,
    scenario_dir: Path,
    scen_cfg: ScenarioConfig,
    inputs_dir: Path,
) -> list[dict[str, Any]]:
    """Stage 2.0.3 (was 2.5.1.b): snapshot each scenario `overlay.apply`
    src into the report's ``inputs/overlay/`` so the report stays
    self-contained even if the scenario yaml mutates later.

    Returns ``[{"src": <as-declared>, "dst": <as-declared>, "size": <bytes>},
                ...]`` for run.json. Silent on individual file errors
    (logged) — a partial snapshot is better than no report.
    """
    out: list[dict[str, Any]] = []
    overlay = scen_cfg.overlay
    if overlay is None or not overlay.apply:
        return out
    dst_root = inputs_dir / "overlay"
    for entry in overlay.apply:
        src_abs = (scenario_dir / entry.src).resolve()
        if not src_abs.is_file():
            logger.warning(
                "overlay src not found, skipping snapshot: %s", src_abs
            )
            continue
        # use src filename as the snapshot path so multiple patches don't
        # collide and the snapshot reads naturally in __reports/<runId>/inputs/.
        snapshot_rel = src_abs.name
        snapshot_dst = dst_root / snapshot_rel
        try:
            snapshot_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_abs, snapshot_dst)
            out.append({
                "src":  entry.src,
                "dst":  entry.dst,
                "path": snapshot_rel,  # legacy field consumed by report.py
                "size": src_abs.stat().st_size,
            })
        except OSError as e:  # pragma: no cover — defensive
            logger.warning("overlay copy failed: %s -> %s: %s",
                           src_abs, snapshot_dst, e)
    return sorted(out, key=lambda x: x["path"])


def _copy_ground_truth(
    *,
    scenario_dir: Path,
    inputs_dir: Path,
) -> list[dict[str, Any]]:
    """Stage 2.5.1.b: copy ground_truth/*.yaml into report inputs/ground_truth/.

    Returns ``[{"name": <stem>, "filename": <basename>, "expected": "pass"|"fail",
                "size": <bytes>}, ...]``. Empty when ground_truth dir missing.
    """
    out: list[dict[str, Any]] = []
    gt_dir = scenario_dir / "ground_truth"
    if not gt_dir.is_dir():
        return out
    dst_root = inputs_dir / "ground_truth"
    dst_root.mkdir(parents=True, exist_ok=True)
    for src in sorted(gt_dir.glob("*.yaml")):
        try:
            shutil.copyfile(src, dst_root / src.name)
            # cheap expected= prefix sniff (pass-*/fail-*) — no yaml parse needed
            stem_lower = src.stem.lower()
            if stem_lower.startswith("pass"):
                expected = "pass"
            elif stem_lower.startswith("fail"):
                expected = "fail"
            else:
                expected = "unknown"
            out.append({
                "name":     src.stem,
                "filename": src.name,
                "expected": expected,
                "size":     src.stat().st_size,
            })
        except OSError as e:  # pragma: no cover — defensive
            logger.warning("ground_truth copy failed: %s: %s", src, e)
    return out


def _render_query(template: str, *, target_path: str) -> str:
    """Substitute `{{ target_path }}` in the scenario query template.

    Deliberately minimal — we do NOT pull in Jinja2 for a single
    variable. Whitespace around the variable name is tolerated so
    ``{{ target_path }}`` and ``{{target_path}}`` both work.
    """
    out = template
    for needle in ("{{ target_path }}", "{{target_path}}"):
        out = out.replace(needle, target_path)
    return out


def _target_path_sha256(root: Path) -> str:
    """Recursively sha256 every file under `root` (sorted by rel path).

    The hash is over the sorted list of ``(rel_path, sha256(file))``
    tuples — that makes the value stable across runs as long as the
    file *contents* and tree shape are identical.

    NOTE: first cut walks every regular file under root. Later we may
    skip `production/` paths that the skill itself is supposed to
    generate (otherwise the post-spawn snapshot would always differ
    from a clean-tree snapshot). TODO(Phase 2.0.4): consider passing
    in an ignore list — but keep it simple until baseline diff actually
    needs it.
    """
    if not root.is_dir():
        return ""
    entries: list[tuple[str, str]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        h = hashlib.sha256()
        try:
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(64 * 1024), b""):
                    h.update(chunk)
        except OSError:
            # unreadable file → skip silently; better than aborting the
            # whole hash computation. The miss will surface as drift on
            # the next run if it becomes readable.
            continue
        entries.append((rel, h.hexdigest()))
    outer = hashlib.sha256()
    for rel, sha in entries:
        outer.update(rel.encode("utf-8"))
        outer.update(b"\0")
        outer.update(sha.encode("ascii"))
        outer.update(b"\n")
    return outer.hexdigest()


def _claude_cli_version() -> str:
    try:
        out = subprocess.check_output(
            ["claude", "--version"], stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _build_prefill_terminator(
    *,
    scenario_dir: Path,
    scen_cfg: ScenarioConfig,
) -> str | None:
    """R-5 治理 C: build a closing assistant text for the forged session.

    Strategy (best-effort, all sources optional):
    1. Read `scenario_dir/baseline/artifacts/<target_path>` — the actual
       prior-turn deliverable. cc reading this in history sees its own
       "previous" final output and is far less likely to redo work.
    2. Fall back to `scenario_dir/baseline/final_text.md` — the cc
       transcript-extracted final assistant text (often empty; design
       §10 M3 known limitation).
    3. Return a minimal stop sentinel when neither source has content.

    The returned text always wraps with a short "任务已完成" prefix so
    cc has an unambiguous signal that the prior turn ended cleanly,
    regardless of which source supplied the body.
    """
    body: str | None = None
    target_path = (scen_cfg.target_path or "").lstrip("/")
    if target_path:
        artifact = scenario_dir / "baseline" / "artifacts" / target_path
        if artifact.is_file():
            try:
                body = artifact.read_text(encoding="utf-8").strip()
            except OSError:
                body = None
    if not body:
        ft = scenario_dir / "baseline" / "final_text.md"
        if ft.is_file():
            try:
                txt = ft.read_text(encoding="utf-8").strip()
                if txt:
                    body = txt
            except OSError:
                body = None

    if body:
        header = f"任务已完成。最终交付物已写入 `{target_path}`：\n\n---\n\n" if target_path else "任务已完成。\n\n"
        return header + body
    # Stop sentinel when no baseline body — still gives cc the end_turn
    # signal so it doesn't drift into continuation mode.
    return f"任务已完成。最终交付物在 `{target_path}`。" if target_path else "任务已完成。"


def _maybe_inject_session(
    *,
    scen_cfg: ScenarioConfig,
    scenario_dir: Path,
    sandbox_root: Path,
    run_id: str,
    rendered_query: str,
    requested_model_hint: str | None,
) -> dict[str, Any] | None:
    """ISS-024 / Stage 2.7.C: opt-in session inject hook.

    Returns None when session_inject is disabled/omitted (default path —
    no behaviour change vs. v1). Otherwise forges the cc session jsonl
    and returns the meta dict that gets stamped into run.json.

    The mismatch warning between scenario.session_inject.schema_version
    and the live cc version is best-effort: we surface it but never
    block (cc may upgrade between scenario authoring and CI runs).
    """
    si = scen_cfg.session_inject
    if si is None or not si.enabled:
        return None

    # Resolve mock_rounds dir (relative to scenario directory).
    mock_dir = (scenario_dir / si.mock_rounds_dir).resolve()
    mock_rounds = si_mod.load_mock_rounds(mock_dir)

    live_cc_version = si_mod.detect_cc_version()
    schema_mismatch = bool(
        si.schema_version
        and live_cc_version != "unknown"
        and si.schema_version != live_cc_version
    )
    if schema_mismatch:
        logger.warning(
            "session_inject.schema_version=%s but live cc=%s — "
            "session jsonl schema may have drifted; if cc rejects "
            "--resume or LLM behaves oddly, re-spike against the new "
            "version and update fixtures",
            si.schema_version, live_cc_version,
        )

    # requested_model_hint comes from scenario.provider.model. When the
    # scenario defers (None), use whatever the runner ends up resolving
    # later — but the injector needs a string NOW, so fall back to a
    # neutral default. The forged assistant.message.model only matters
    # for cc's prefill parsing; spike showed it tolerates any reasonable
    # model string.
    model_for_forge = requested_model_hint or "claude-opus-4-7"

    injector = si_mod.SessionFileInjector(
        sandbox_root=sandbox_root,
        cc_version=live_cc_version,
        requested_model=model_for_forge,
    )
    # R-5 治理 C (design §16.7.12): read baseline target artifact and
    # synthesize a closing assistant message so cc resume sees a
    # complete prior turn (stop_reason=end_turn). Without this cc reads
    # the unfinished tool_result chain as "previous turn never produced
    # an assistant answer" and continues — the R-5 escape window.
    final_assistant_text = _build_prefill_terminator(
        scenario_dir=scenario_dir,
        scen_cfg=scen_cfg,
    )
    session_id = injector.create_session_with_mock_history(
        user_input=rendered_query,
        mock_rounds=mock_rounds,
        run_id=run_id,
        final_assistant_text=final_assistant_text,
    )
    forged_path = si_mod.session_file_path(sandbox_root, session_id)

    # M5 (P3 双保险 outer ring): derive the disallow list from the
    # mocked-tool set. Each tool that has at least one mock round in
    # this scenario gets denied at the cc CLI layer, so even if the
    # model tries to escape the forged history it gets refused before
    # the network call. Order is stable (first-seen order across rounds)
    # for deterministic run.json diffs.
    #
    # R-5 治理 B (design §16.7.5): also ban cc-builtin external tools
    # (`WebSearch` / `WebFetch`) that the model commonly reaches for
    # when the mock-named tool is denied. Without this the model
    # escapes to e.g. `WebSearch` (returns empty) or `WebFetch` (cc
    # security policy denies non-allowlisted hosts) and burns the
    # provider timeout on rate_limit retries instead of finishing.
    # `Bash` is NOT auto-added — it's so common in scenarios it would
    # be banned by the mock-derived set anyway; auto-adding would also
    # break the rare scenario that records zero Bash but legitimately
    # wants Bash live during replay.
    disallowed_tools: list[str] = []
    seen_tools: set[str] = set()
    for mr in mock_rounds:
        if mr.tool_name not in seen_tools:
            disallowed_tools.append(mr.tool_name)
            seen_tools.add(mr.tool_name)
    for builtin in CC_BUILTIN_EXTERNAL_TOOLS_TO_BAN:
        if builtin not in seen_tools:
            disallowed_tools.append(builtin)
            seen_tools.add(builtin)

    return {
        "injected_session_id":   session_id,
        "mock_rounds_dir":       str(si.mock_rounds_dir),
        "round_count":           len(mock_rounds),
        "round_ids":             [r.round_id for r in mock_rounds],
        "cc_cli_version":        live_cc_version,
        "session_schema_version": si.schema_version,
        "schema_version_mismatch": schema_mismatch,
        "forged_jsonl_path":     str(forged_path),
        # M5: outer-ring disallow list; runner reads this back to pass
        # to provider.run_provider(disallowed_tools=...).
        "disallowed_tools":      disallowed_tools,
    }


def _cleanup_session_file(sandbox_root: Path, session_id: str) -> None:
    """ISS-024 / Stage 2.7.D inline: remove the forged session jsonl.

    Takes `session_id` (not `run_id`) because cc resolves --resume by
    filename `<session_id>.jsonl` — see session_inject.session_file_path
    docstring. Caller must pass the id returned by
    SessionFileInjector.create_session_with_mock_history.

    Best-effort: a missing file is fine; permission errors are logged
    but don't propagate so runner teardown stays robust. Stage 2.7.D
    adds a separate `onecxt eval clean` sweep for residue across runs.
    """
    try:
        target = si_mod.session_file_path(sandbox_root, session_id)
    except Exception:  # pragma: no cover — defensive
        return
    if not target.exists():
        return
    try:
        target.unlink()
    except OSError as e:
        logger.warning("failed to cleanup forged session file %s: %s", target, e)
        return
    # If the project-hash directory is now empty, prune it too.
    parent = target.parent
    try:
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:  # pragma: no cover — defensive
        pass


def _enrich_tool_call_durations(
    tool_calls: list[dict[str, Any]], events: list[dict[str, Any]],
) -> None:
    """从 events_list 的 tool_use / tool_result 时间戳计算真实 duration_ms.

    Stage 2.5.3: stream-json.jsonl 已注入 ``_t`` (epoch ms)。events.py
    把它传播为 ``t_ms``。本函数在 events 中配对 ``tool_use`` →
    ``tool_result``，把 wall-time duration 写回对应的 tool_call dict。
    没有匹配到的事件保持原样（judge 不读 duration，Gantt 会 fallback
    到 0）。
    """
    if not events:
        return
    starts: dict[str, float] = {}
    ends: dict[str, float] = {}
    for ev in events:
        kind = ev.get("kind")
        t_ms = ev.get("t_ms")
        if t_ms is None:
            continue
        tid = ev.get("tool_use_id")
        if not tid:
            continue
        if kind == "tool_use":
            starts[tid] = t_ms
        elif kind == "tool_result":
            ends[tid] = t_ms

    base_t = next((ev["t_ms"] for ev in events if ev.get("t_ms") is not None), None)
    for tc in tool_calls:
        tid = tc.get("tool_use_id")
        if tid and tid in starts and tid in ends:
            dur = max(0, int(ends[tid] - starts[tid]))
            tc["duration_ms"] = dur
            if base_t is not None:
                tc["start_offset_ms"] = max(0, int(starts[tid] - base_t))
        else:
            if "duration_ms" not in tc:
                tc["duration_ms"] = 0
            if "start_offset_ms" not in tc:
                tc["start_offset_ms"] = 0


@dataclass
class RunOutcome:
    overall: str  # "PASS" | "FAIL"
    run_id: str
    report_dir: Path
    run_json_path: Path
    report_html_path: Path
    sandbox_path: Path
    kept_sandbox: bool


def _single_run(
    *,
    repo_root: Path,
    skill: str,
    scenario: str,
    scenario_dir: Path,
    skill_cfg: SkillEvalConfig,
    scen_cfg: ScenarioConfig,
    keep_tmp: bool,
    skill_override: Path | None,
    with_diff: bool = False,
) -> dict[str, Any]:
    """Run one iteration; return the run.json dict (also written to disk)."""
    # 1. sandbox — Stage 2.0.1 contract: prepare(run_id, *, repo_root=...,
    #    force_driver=..., include_git=..., sandbox_includes=...).
    run_id = sb_mod.new_run_id()
    sandbox = sb_mod.prepare(
        run_id,
        repo_root=repo_root,
        force_driver=getattr(scen_cfg, "sandbox_driver", None),
        include_git=scen_cfg.include_git,
        sandbox_includes=getattr(scen_cfg, "sandbox_includes", None),
    )
    # ISS-020: spawn cwd is the sandbox root (≡ repo root); the scenario
    # target_path tells artifacts/judge where to look but does NOT change
    # where cc is launched.
    spawn_cwd = sandbox.path
    # `target_path` is the post-compat canonical value; the scenario_config
    # validator mirrors deprecated `cwd` into it for us.
    target_path = scen_cfg.target_path or ""
    artifacts_base = (sandbox.path / target_path).resolve() if target_path else sandbox.path

    report_dir = scenario_dir / "__reports" / sandbox.run_id
    report_dir.mkdir(parents=True, exist_ok=True)

    overlay_applied: list[fix_mod.OverlayApplied] = []
    skill_override_meta: dict | None = None
    # ISS-024 / Stage 2.7.C: hoist injected session_id into the outer scope
    # so the finally block can clean up `<session_id>.jsonl` even if the try
    # body raises before session_inject_meta gets assigned.
    injected_session_id: str | None = None

    try:
        # 1.5 (Stage 2.6) skill override BEFORE fixture overlay.
        # tech_design §10.5 contract: skill_override = {dir, sha256_per_file}.
        # `eval.yaml` and `evals/` are NOT in the override scope (the
        # evaluation set is the baseline; a candidate can't change it).
        if skill_override is not None:
            sk_dst = sandbox.path / "skills" / skill
            if not skill_override.is_dir():
                raise FileNotFoundError(f"--skill-override missing: {skill_override}")
            sha_per_file: dict[str, str] = {}
            for src in skill_override.rglob("*"):
                if src.is_dir():
                    continue
                rel = src.relative_to(skill_override)
                rel_str = str(rel).replace("\\", "/")
                # Refuse to override the evaluation set itself (§10.5).
                if rel_str == "eval.yaml" or rel_str.startswith("evals/"):
                    logger.warning(
                        "skill_override refuses to replace %s (evaluation "
                        "set is baseline, not candidate territory)", rel_str,
                    )
                    continue
                dst = sk_dst / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                h = hashlib.sha256()
                with src.open("rb") as f:
                    for chunk in iter(lambda: f.read(64 * 1024), b""):
                        h.update(chunk)
                sha_per_file[rel_str] = h.hexdigest()
            skill_override_meta = {
                "dir": str(skill_override),
                "sha256_per_file": sha_per_file,
            }

        # 2. overlay (ISS-022, Stage 2.0.3) — single-file patches on top
        #    of the shared fixture referenced by `target_path`. The
        #    fixture itself lives at `<repo_root>/<target_path>` and is
        #    already inside the sandbox (sandbox.prepare snapshots the
        #    whole tree). The overlay layer is OPTIONAL.
        overlay_applied = fix_mod.apply_overlay(
            sandbox_root=sandbox.path,
            target_path=target_path,
            overlay=scen_cfg.overlay,
            scenario_dir=scenario_dir,
        )

        # 3. pre-snapshot — artifacts globs resolve under target_path
        patterns = scen_cfg.artifacts_override or skill_cfg.artifacts
        pre = art_mod.snapshot(artifacts_base, patterns) if patterns else {}

        # 3.5 record the target_path subtree hash BEFORE spawn (so it
        # reflects the input feature state, not whatever the skill
        # writes during the run).
        target_path_sha = _target_path_sha256(artifacts_base)

        # 4. spawn provider — provider itself does not raise for normal
        #    failures (timeout / api_error / empty_stdout / other). We only
        #    catch KeyboardInterrupt here so a Ctrl-C during a long
        #    provider run still produces a run.json + report.html
        #    (ISS-019 / Stage 1.1.8).
        stream_path = report_dir / "stream-json.jsonl"
        rendered_query = _render_query(scen_cfg.query, target_path=target_path)

        # 4.0 Session File Injection (ISS-024 / Stage 2.7.C) — opt-in via
        #     scenario.session_inject.enabled. When on, forge
        #     ~/.claude/projects/<hash>/onecxt-eval-<runId>.jsonl with
        #     mock_rounds so `cc --resume <id>` sees the (tool_use,
        #     tool_result) pairs as past history and won't re-invoke the
        #     mocked tools. See tech_design.md §4. Returns None when the
        #     scenario disables/omits session_inject (default behaviour).
        session_inject_meta = _maybe_inject_session(
            scen_cfg=scen_cfg,
            scenario_dir=scenario_dir,
            sandbox_root=sandbox.path,
            run_id=sandbox.run_id,
            rendered_query=rendered_query,
            requested_model_hint=scen_cfg.provider.model,
        )
        resume_session_id = (
            session_inject_meta["injected_session_id"]
            if session_inject_meta else None
        )
        # Mirror into the outer-scope var so finally:cleanup can find it.
        injected_session_id = resume_session_id
        # M5 (P3 双保险 outer ring): hand the disallow list to the provider so
        # `claude -p ... --disallowedTools <csv>` blocks real tool calls even
        # if cc escapes the forged history. See recording-mode-design.md §12.3.
        disallowed_tools_for_provider = (
            session_inject_meta["disallowed_tools"]
            if session_inject_meta else None
        )

        # Stage 2.X.6: model profile dispatch.
        # scenario.provider.model 同时承担"模型选择 + settings 文件选择"两重语义。
        # 通过 model_profiles 表把 "glm-5.1" / "kimi-2.6" 这类 key 映射到
        # 对应 settings.json 路径；老 scenario 不写 provider.model 时兜底走 CCD2。
        from one_context.eval.model_profiles import resolve_settings_path as _resolve_profile_settings
        try:
            profile_settings_path = _resolve_profile_settings(scen_cfg.provider.model)
        except ValueError as e:
            raise RuntimeError(f"cannot resolve model profile: {e}") from e

        # Stage 2.X.4: resolve effective model name (传给 claude --model).
        # 走 profile settings 的 env.ANTHROPIC_MODEL 作为权威值。
        from one_context.eval.judge import _resolve_settings_path
        from one_context.eval.settings_resolver import (
            ModelResolveError,
            resolve_effective_model,
        )
        try:
            resolved = resolve_effective_model(
                yaml_model=None,  # profile 优先；不让 scenario.model 二次冒充模型名
                settings_path=profile_settings_path,
            )
        except ModelResolveError as e:
            raise RuntimeError(f"cannot resolve provider model: {e}") from e
        effective_model = resolved.model
        model_source = resolved.source

        # 把 profile settings path 通过 env 传给子进程 provider（claude-code.js
        # 读取 $ONECXT_CLAUDE_SETTINGS 并 append --settings <path>）。
        os.environ["ONECXT_CLAUDE_SETTINGS"] = profile_settings_path


        try:
            prov = provider_mod.run_provider(
                repo_root=repo_root,
                query=rendered_query,
                cwd=spawn_cwd,
                model=effective_model,
                permission_mode=scen_cfg.provider.permissionMode,
                timeout_ms=scen_cfg.provider.timeoutMs,
                stream_path=stream_path,
                resume_session_id=resume_session_id,
                disallowed_tools=disallowed_tools_for_provider,
            )
        except KeyboardInterrupt:
            prov = provider_mod.ProviderResult(
                ok=False,
                exit_code=-1,
                duration_ms=0,
                requested_model=effective_model,
                actual_model=None,
                final_text="",
                tool_calls=[],
                stream_path=str(stream_path),
                provider_status=provider_mod.PROVIDER_STATUS_INTERRUPTED,
                cost_usd=provider_mod.extract_cost_usd(stream_path),
                timeout=False,
                stderr_tail="(KeyboardInterrupt — runner caught)",
                raw=None,
            )

        provider_failed = prov.provider_status != provider_mod.PROVIDER_STATUS_OK

        # 5. post-snapshot — still try even if provider failed (some files
        #    may have been written before the crash; helps debugging).
        try:
            post = art_mod.snapshot(artifacts_base, patterns) if patterns else {}
            adiff = art_mod.diff(pre, post)
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("post-snapshot failed: %s", e)
            adiff = art_mod.ArtifactDiff()

        # 6. ship artifacts into report dir (preserve target_path-relative tree)
        report_artifacts_dir = report_dir / "artifacts"
        if adiff.produced:
            try:
                art_mod.copy_into_report(artifacts_base, adiff.produced, report_artifacts_dir)
            except Exception as e:  # pragma: no cover — defensive
                logger.warning("copy_into_report failed: %s", e)

        artifacts_for_judge: list[dict[str, Any]] = []
        for snap in adiff.produced:
            full = artifacts_base / snap.rel_path
            artifacts_for_judge.append({
                "path": snap.rel_path,
                "size": snap.size,
                "sha256": snap.sha256,
                "head": _read_head(full),
                "source": "produced",
            })

        # R-10 治理 a (design §16.7.13): after C terminator landed, cc
        # stops re-running the mock pipeline and emits no new artifacts.
        # Judge then sees `artifacts: (none)` and trips F3-style
        # "pipeline incomplete" rules even though the mock baseline
        # carries the canonical prior-turn deliverable. Feed baseline
        # artifacts with `source: baseline` so the judge has the full
        # picture; the judge prompt explains the distinction.
        baseline_arts_dir = scenario_dir / "baseline" / "artifacts"
        if baseline_arts_dir.is_dir():
            for bf in sorted(baseline_arts_dir.rglob("*")):
                if not bf.is_file():
                    continue
                rel = bf.relative_to(baseline_arts_dir).as_posix()
                # Don't shadow produced files of the same rel_path —
                # cc's fresh write is the authoritative version.
                produced_rels = {a["path"] for a in artifacts_for_judge}
                if rel in produced_rels:
                    continue
                try:
                    size = bf.stat().st_size
                except OSError:
                    continue
                artifacts_for_judge.append({
                    "path": rel,
                    "size": size,
                    "sha256": _file_sha256(bf),
                    "head": _read_head(bf),
                    "source": "baseline",
                })

        # 6.5 (Phase 2.6.B) declarative assertions — pre-LLM check.
        # Run every spec (no short-circuit) so the report shows the
        # full picture, then short-circuit the LLM judge if any
        # `blocking=True` assertion did not pass. `merge_assertions`
        # raises ValueError on scenario↔skill id collisions; that's
        # treated like a config error (kept fatal so misconfigured
        # eval.yaml/scenario.yaml fails fast at run time).
        merged_specs = assertions_mod.merge_assertions(
            skill_cfg.assertions, scen_cfg.assertions, scen_cfg.assertions_skip,
        )
        assertion_ctx = assertions_mod.AssertionContext(
            sandbox_root=sandbox.path,
            artifacts_base=artifacts_base,
            final_text=prov.final_text or "",
            stdout="",  # provider doesn't surface raw stdout; final_text already covers it
            stderr_tail=prov.stderr_tail or "",
            tool_calls=prov.tool_calls,
            produced_paths={s.rel_path for s in adiff.produced},
        )
        assertion_results = assertions_mod.run_assertions(merged_specs, assertion_ctx)
        assertion_summary = assertions_mod.summarize(assertion_results)
        blocking_assertion_failed = assertion_summary["blocking_failed"] > 0

        # 7. judge — skip entirely when blocking assertion failed
        #    (deterministic verdict; saves token). When provider failed
        #    but P3 all passed, R-5 治理 D (design §16.7.5) keeps the
        #    judge in the loop with a status notice so the report shows
        #    partial progress instead of a blank skipped tag. overall_pass
        #    still requires prov.ok=True, so a timeout is still a fail.
        criteria = judge_mod.merge_rubric(
            skill_cfg.default_rubric, scen_cfg.rubric,
        )
        provider_status_notice: str | None = None
        if blocking_assertion_failed:
            judge_block: dict[str, Any] = {
                "skipped": "blocking_assertion_failed",
                "failed_ids": [
                    r.id for r in assertion_results
                    if r.blocking and r.status != "pass"
                ],
            }
            overall_pass = False
        else:
            if provider_failed:
                provider_status_notice = (
                    f"本次 provider 状态 = {prov.provider_status}"
                    f"（duration={prov.duration_ms}ms, exit_code={prov.exit_code}）。"
                    "cc 没有产出完整 final_text，但 P3 双保险断言全过"
                    "（未真调被 disallow 的工具）。请基于已发生的 tool_calls "
                    "与 partial final_text + baseline artifacts 评估进度："
                    "完全没进度 → 0；做了一部分 → 按完成度评；"
                    "如果 baseline artifacts 已包含目标产物（mock 阶段产出"
                    "在 workspace 里），且核心步骤显示在 tool_calls 中，可酌情给高分。"
                )
            judge_cache_dir = report_dir / "judge-cache"
            # Stage 2.X.5: judge now ALWAYS uses the provider's effective model,
            # not a separate `judge_model` from eval.yaml. If skill_cfg.judge_model
            # is still set, surface a deprecation warning but ignore it.
            if (
                skill_cfg.judge_model
                and skill_cfg.judge_model.strip()
                and skill_cfg.judge_model != effective_model
            ):
                logger.warning(
                    "eval.yaml judge_model=%r is deprecated and IGNORED; "
                    "judge now uses provider's effective model (%r). "
                    "Remove judge_model from eval.yaml to silence this warning.",
                    skill_cfg.judge_model, effective_model,
                )
            judge_res = judge_mod.evaluate(
                criteria=criteria,
                final_text=prov.final_text,
                tool_calls=prov.tool_calls,
                artifacts=artifacts_for_judge,
                cache_dir=judge_cache_dir,
                model=effective_model,
                provider_status_notice=provider_status_notice,
            )
            judge_block = {
                "model": judge_res.model,
                "pass": judge_res.pass_,
                "score": judge_res.score,
                "reason": judge_res.reason,
                "criteria": criteria,
                "cached": judge_res.cached,
            }
            if provider_status_notice:
                judge_block["provider_status_notice"] = provider_status_notice
            score_passes = judge_res.score >= scen_cfg.threshold
            overall_pass = judge_res.pass_ and score_passes and prov.ok

        # 7.5 (Stage 2.5.1.b) Snapshot scenario inputs to make report
        #     self-contained: copy fixture overlay files + ground_truth/*.yaml
        #     to __reports/<runId>/inputs/. The repo files may rotate later;
        #     a stand-alone report must still show what was fed to the agent.
        inputs_dir = report_dir / "inputs"
        overlay_files_meta = _copy_overlay_files(
            scenario_dir=scenario_dir,
            scen_cfg=scen_cfg,
            inputs_dir=inputs_dir,
        )
        ground_truth_files_meta = _copy_ground_truth(
            scenario_dir=scenario_dir,
            inputs_dir=inputs_dir,
        )

        # 7.6 (Stage 2.5.1.c) Parse stream-json.jsonl into a flat event list
        #     so the report can render a real execution timeline
        #     (think → tool_use → tool_result → text) instead of treating
        #     tool calls as if they were back-to-back.
        try:
            events_list = events_mod.parse_stream_json(stream_path)
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("events parse failed: %s", e)
            events_list = []

        # 7.7 (Stage 2.5.3) 用 events 时间戳给 tool_calls 注入真实 duration_ms
        _enrich_tool_call_durations(prov.tool_calls, events_list)

        # 8. assemble run.json
        actual_model = prov.actual_model or ""
        model_drift = bool(actual_model) and actual_model != prov.requested_model

        # Stage 2.0.1 fills these on Sandbox; fall back gracefully if the
        # sandbox.py version in this checkout is older than this runner.
        working_tree_sha = getattr(sandbox, "working_tree_sha", "")
        sandbox_driver = getattr(sandbox, "driver", "")

        run = {
            "run_schema_version": "1",
            "skill": skill,
            "scenario": scenario,
            "run_id": sandbox.run_id,
            "timestamp": report_mod.now_iso(),
            "git_commit": sandbox.git_commit,
            "working_tree_sha": working_tree_sha,
            "sandbox_driver": sandbox_driver,
            "git_user_email": _git_user_email(repo_root),
            "claude_cli_version": _claude_cli_version(),
            "requested_model": prov.requested_model,
            "actual_model": actual_model,
            "model_drift": model_drift,
            # ISS-020: target_path is the canonical field; keep `cwd`
            # mirroring it so legacy readers (Phase 1 reports / external
            # tooling) keep working until we cut the alias.
            "target_path": target_path,
            "target_path_sha256": target_path_sha,
            "cwd": target_path,
            # ISS-022: `fixture_mode` is gone; overlay is single-file
            # patches with replace semantics. Keep an empty list under
            # `overlay_added` for backward-compat report rendering
            # (Phase 2.5 dashboard reads it); the canonical new field is
            # `overlay_applied`.
            #
            # NOTE: `a.dst` was produced by `fixture.apply_overlay` which
            # resolves `sandbox_root` (line 89 of fixture.py). On macOS
            # `/tmp` → `/private/tmp` symlink resolution makes `a.dst`
            # start with `/private/tmp/...` while `sandbox.path` is still
            # the un-resolved `/tmp/...`. We MUST resolve sandbox.path
            # here too, otherwise `relative_to()` raises
            # "is not in the subpath of" on every macOS run that uses
            # `overlay.apply`. (pytest's `tmp_path` already hands back a
            # resolved path, which is why the existing e2e tests didn't
            # catch this.)
            "overlay_applied": [
                {
                    "src":    str(a.src),
                    "dst":    str(a.dst.relative_to(sandbox.path.resolve())),
                    "sha256": a.sha256,
                }
                for a in overlay_applied
            ],
            "overlay_added": [
                str(a.dst.relative_to(sandbox.path.resolve())) for a in overlay_applied
            ],
            "duration_ms": prov.duration_ms,
            "cost_usd": prov.cost_usd,
            "provider_status": prov.provider_status,
            "exit_code": prov.exit_code,
            "timeout": prov.timeout,
            "stderr_tail": prov.stderr_tail,
            "tool_calls": prov.tool_calls,
            "final_text": prov.final_text,
            "artifacts": [
                {
                    "path": a["path"],
                    "size": a["size"],
                    "sha256": a["sha256"],
                    "source": a.get("source", "produced"),
                }
                for a in artifacts_for_judge
            ],
            "deleted_artifacts": adiff.deleted,
            "assertions": [
                {
                    "id":          r.id,
                    "kind":        r.kind,
                    "status":      r.status,
                    "blocking":    r.blocking,
                    "message":     r.message,
                    "detail":      r.detail,
                    "duration_ms": r.duration_ms,
                }
                for r in assertion_results
            ],
            "assertions_summary": assertion_summary,
            "judge": judge_block,
            "threshold": scen_cfg.threshold,
            "repeat": {"total": 1, "passed": int(overall_pass), "pass_rate": float(int(overall_pass))},
            "overall": "PASS" if overall_pass else "FAIL",
            # ── Stage 2.5.1 additions ──
            "scenario_inputs": {
                "query":            scen_cfg.query,
                "query_rendered":   rendered_query,
                "description":      scen_cfg.description,
                "target_path":      target_path,
                "rubric_default":   skill_cfg.default_rubric,
                "rubric_addition":  scen_cfg.rubric,
                "provider": {
                    "model":           effective_model,
                    "model_source":    model_source,
                    "model_yaml":      scen_cfg.provider.model,
                    "permissionMode":  scen_cfg.provider.permissionMode,
                    "timeoutMs":       scen_cfg.provider.timeoutMs,
                },
                "overlay_files":      overlay_files_meta,
                "ground_truth_files": ground_truth_files_meta,
            },
            "events": events_list,
        }
        if skill_override_meta is not None:
            run["skill_override"] = skill_override_meta
        if session_inject_meta is not None:
            # ISS-024 / Stage 2.7.C: full Stage 2.7.E (baseline diff + digest
            # comparison) will broaden this meta with mock_rounds_digest etc;
            # for now we surface enough for the report to mark "session was
            # forged" and for downstream tooling to find the injected jsonl.
            run["session_inject"] = session_inject_meta

        # Stage 2.2: when --diff was requested, compute the baseline
        # diff and embed it under `baseline_diff` so the report can
        # render the Diff tab. The runner deliberately tolerates a
        # missing baseline (returns has_baseline=False) so `--diff`
        # is safe to leave on by default in scripts.
        if with_diff:
            try:
                baseline = diff_mod.load_baseline(scenario_dir)
                run["baseline_diff"] = diff_mod.compute(
                    current_run=run,
                    baseline_run=baseline,
                )
            except Exception as e:  # pragma: no cover — defensive
                logger.warning("baseline diff failed: %s", e)
                run["baseline_diff"] = {
                    "has_baseline": False,
                    "note": f"diff computation failed: {e}",
                }

        report_mod.write_run_json(run, report_dir / "run.json")
        report_mod.render(run, report_dir / "report.html")
        run["_report_dir"] = str(report_dir)
        return run

    finally:
        sb_mod.teardown(sandbox, keep=keep_tmp)
        # ISS-024 / Stage 2.7.C: drop the forged ~/.claude/projects/<hash>/
        # <session_id>.jsonl so the user's session list isn't polluted.
        # --keep-tmp leaves it for debugging (matches sandbox teardown semantics).
        # No-op when session inject wasn't enabled (injected_session_id is None).
        if not keep_tmp and injected_session_id:
            _cleanup_session_file(sandbox.path, injected_session_id)


def run(
    *,
    repo_root: Path,
    target: str,
    keep_tmp: bool = False,
    skill_override: Path | None = None,
    with_diff: bool = False,
    prune_on_pass: bool = True,
) -> RunOutcome:
    """Run a `<skill>/<scenario>`; honor `repeat` if > 1.

    When `prune_on_pass=True` (default) and the aggregate outcome is PASS
    on a non-`skill_override` run, prune older `__reports/<runId>/` dirs
    so only the current run survives. Tests that exercise multiple runs
    in the same scenario dir should pass `prune_on_pass=False`.
    """
    skill, scenario, skill_dir, scenario_dir, skill_cfg, scen_cfg = (
        _resolve_skill_and_scenario(repo_root, target)
    )

    runs: list[dict[str, Any]] = []
    for _ in range(scen_cfg.repeat):
        runs.append(_single_run(
            repo_root=repo_root,
            skill=skill,
            scenario=scenario,
            scenario_dir=scenario_dir,
            skill_cfg=skill_cfg,
            scen_cfg=scen_cfg,
            keep_tmp=keep_tmp,
            skill_override=skill_override,
            with_diff=with_diff,
        ))

    if scen_cfg.repeat == 1:
        last = runs[-1]
    else:
        # repeat > 1: pass rate ≥ 2/3 => PASS
        passed = sum(1 for r in runs if r["overall"] == "PASS")
        rate = passed / len(runs)
        overall = "PASS" if rate >= 2 / 3 else "FAIL"
        last = runs[-1]
        last["repeat"] = {"total": len(runs), "passed": passed, "pass_rate": rate}
        last["overall"] = overall
        # rewrite the last run's run.json + report.html so it reflects the
        # aggregated repeat outcome
        report_mod.write_run_json(last, Path(last["_report_dir"]) / "run.json")
        report_mod.render(last, Path(last["_report_dir"]) / "report.html")

    # PASS-rolling: keep only the current runId; FAIL accumulates until
    # the next PASS sweeps it. `skill_override` runs are debug artifacts
    # (baseline.py refuses to snapshot them) so they must not clear real
    # history either. With `repeat > 1`, every iteration shares the same
    # unix-second prefix; pass the intermediate runIds explicitly so the
    # "strictly less than" cutoff doesn't leave them behind.
    if (
        prune_on_pass
        and last["overall"] == "PASS"
        and not last.get("skill_override")
    ):
        intermediates = frozenset(
            r["run_id"] for r in runs if r["run_id"] != last["run_id"]
        )
        _prune_reports_after_pass(
            scenario_dir,
            keep_run_id=last["run_id"],
            extra_to_remove=intermediates,
        )

    return RunOutcome(
        overall=last["overall"],
        run_id=last["run_id"],
        report_dir=Path(last["_report_dir"]),
        run_json_path=Path(last["_report_dir"]) / "run.json",
        report_html_path=Path(last["_report_dir"]) / "report.html",
        sandbox_path=Path("/tmp") / f"onecxt-eval-{last['run_id']}",
        kept_sandbox=keep_tmp,
    )


# ---------------------------------------------------------------------------
# discovery & cleanup helpers (used by `onecxt eval list` / `clean`)
# ---------------------------------------------------------------------------

def list_scenarios(repo_root: Path) -> list[tuple[str, str]]:
    """Return [(skill, scenario), ...] for every scenario.yaml in tree."""
    out: list[tuple[str, str]] = []
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return out
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        evals = skill / "evals"
        if not evals.is_dir():
            continue
        for scn in sorted(p for p in evals.iterdir() if p.is_dir()):
            if (scn / "scenario.yaml").is_file():
                out.append((skill.name, scn.name))
    return out


def clean_reports(repo_root: Path) -> int:
    """Remove every `__reports/` dir under `skills/*/evals/*/`. Returns count."""
    removed = 0
    for skill, scn in list_scenarios(repo_root):
        rd = repo_root / "skills" / skill / "evals" / scn / "__reports"
        if rd.is_dir():
            shutil.rmtree(rd, ignore_errors=True)
            removed += 1
    return removed


def _prune_reports_after_pass(
    scenario_dir: Path,
    *,
    keep_run_id: str,
    extra_to_remove: frozenset[str] = frozenset(),
) -> int:
    """Delete `__reports/<runId>/` dirs strictly older than `keep_run_id`
    (plus any runIds explicitly listed in `extra_to_remove`), plus
    `__reports/index.html`. Returns the number of items removed.

    Concurrency: runId format is `<unix_seconds>-<6char>` (sandbox.new_run_id),
    so we use the seconds prefix as cutoff and only remove dirs whose
    prefix is *strictly less than* the current run's. A concurrent run
    started in the same second or later survives, since its prefix is
    >= cutoff. Dirs whose name does not parse as `<int>-...` are skipped
    (defensive against future runId format changes / user-placed dirs).

    `extra_to_remove` carves out an exception for `repeat > 1` aggregate
    runs: every `_single_run` in the repeat loop generates its own runId
    in the same second, so the "strictly less than" rule alone would
    leave the intermediate iterations behind. The runner passes the set
    of intermediate runIds it produced — they are runner-owned by
    construction, so deleting them is safe even though their prefix
    equals the cutoff.
    """
    reports_dir = scenario_dir / "__reports"
    if not reports_dir.is_dir():
        return 0
    keep_dir = reports_dir / keep_run_id
    if not keep_dir.is_dir():
        return 0
    try:
        cutoff = int(keep_run_id.split("-", 1)[0])
    except (ValueError, IndexError):
        return 0

    removed = 0
    for entry in reports_dir.iterdir():
        if entry.name == keep_run_id:
            continue
        if entry.is_dir():
            try:
                prefix = int(entry.name.split("-", 1)[0])
            except (ValueError, IndexError):
                continue
            should_remove = (
                prefix < cutoff or entry.name in extra_to_remove
            )
            if should_remove:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        elif entry.name == "index.html":
            try:
                entry.unlink()
                removed += 1
            except OSError:
                pass
    return removed
