"""Session File Injection — v2 fixture main path (ISS-024 / Stage 2.7).

This module provides:

1. `MockRound` — pydantic model for one mocked (tool_use, tool_result) pair
2. `load_mock_rounds(dir_path)` — load all `<round>.yaml` files in a
   directory in lexical order, validate, and return a list[MockRound]
3. `SessionFileInjector` — forge a cc session jsonl file under
   `~/.claude/projects/<hash>/onecxt-eval-<run_id>.jsonl` so that
   `claude --resume <session_id>` loads the forged history and skips
   re-invoking the mocked tools (Stage 2.7.B)
4. `detect_cc_version()` — `claude --version` parsed + cached for
   `SessionInjectConfig.schema_version` mismatch warnings (Stage 2.7.B.2)

See tech_design.md §4 + session-injection-spike-result.md for the full
design and the cc 2.1.156 jsonl schema this module targets.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# tool_result is serialized into the forged jsonl. Hard-limit the
# per-round payload to keep session files small (cc slows down on huge
# prefill, and the runner does a pre-spawn safety check on total session
# file size separately — see tech_design §4.9 R2).
MAX_TOOL_RESULT_BYTES = 1_000_000  # 1 MB per round


class MockRound(BaseModel):
    """One round of forged cc history.

    Maps to three jsonl lines when injected:
        user (text)         — the original user query (written once, by the
                              injector, NOT per round — kept here only as
                              context-bearing metadata for the first round)
        assistant (tool_use)— faked cc tool invocation
        user (tool_result)  — faked tool return = **the mock**

    `round_id` is the stable identifier the baseline digest pins on
    (mock_rounds_digest = {round_id: sha256(yaml_file)}). It must be
    globally unique within a `mock_rounds/` directory; the loader rejects
    duplicates fail-fast.

    `tool_name` is the cc-side tool name as it appears in stream-json
    (e.g. "WebFetch", "Bash", "Read"). The runner does NOT validate it
    against a hardcoded tool list — cc's tool set is plugin-extensible
    and we want to support MCP tool names like
    `mcp__plugin_playwright_playwright__browser_navigate` too.

    `tool_result` is the value the forged user(tool_result) message will
    carry as `content`. It can be str / dict / list — the injector
    serializes non-strings via `json.dumps(ensure_ascii=False)` before
    writing.

    `boundary_type` distinguishes local cc tools from MCP-bridged ones;
    the injector treats them identically for now but the field is
    surfaced in the HTML report (Stage 2.7.I).
    """
    model_config = ConfigDict(extra="forbid")

    round_id: str
    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_result: str | dict[str, Any] | list[Any]
    assistant_thinking: str = ""
    boundary_type: Literal["local_tool", "mcp_call"] = "local_tool"

    @field_validator("round_id")
    @classmethod
    def _round_id_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("round_id must not be empty")
        return v

    @field_validator("tool_name")
    @classmethod
    def _tool_name_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("tool_name must not be empty")
        return v

    @field_validator("tool_result")
    @classmethod
    def _tool_result_size(cls, v: Any) -> Any:
        # Estimate serialized size; strings count their utf-8 byte length,
        # collections go through json.dumps to mirror what the injector
        # will write.
        if isinstance(v, str):
            size = len(v.encode("utf-8"))
        else:
            size = len(json.dumps(v, ensure_ascii=False).encode("utf-8"))
        if size > MAX_TOOL_RESULT_BYTES:
            raise ValueError(
                f"tool_result is {size} bytes; per-round cap is "
                f"{MAX_TOOL_RESULT_BYTES} bytes. Trim the fixture (drop "
                f"irrelevant fields / keep only Top-N entries) so the "
                f"forged session file stays small."
            )
        return v


def load_mock_rounds(dir_path: Path) -> list[MockRound]:
    """Load every `*.yaml` / `*.yml` file in `dir_path` as a MockRound.

    Files are sorted by name (lexical), and that order is the round
    order at injection time. So authors should use a numeric prefix
    convention like `round-01-hn-fetch.yaml`, `round-02-blog-fetch.yaml`,
    etc.

    Raises:
        FileNotFoundError: dir_path does not exist or is not a directory
        ValueError: any file fails schema validation, OR two files share
            the same round_id (would corrupt mock_rounds_digest semantics)
    """
    if not dir_path.is_dir():
        raise FileNotFoundError(
            f"mock_rounds_dir not found: {dir_path} "
            f"(make sure session_inject.mock_rounds_dir is correct relative "
            f"to the scenario directory)"
        )

    files = sorted(
        [p for p in dir_path.iterdir()
         if p.is_file() and p.suffix in (".yaml", ".yml")]
    )

    rounds: list[MockRound] = []
    seen_ids: dict[str, Path] = {}
    for f in files:
        try:
            raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ValueError(f"{f}: invalid YAML — {e}") from e
        if not isinstance(raw, dict):
            raise ValueError(
                f"{f}: expected a YAML mapping at top level, got {type(raw).__name__}"
            )
        try:
            mr = MockRound.model_validate(raw)
        except Exception as e:
            raise ValueError(f"{f}: schema validation failed — {e}") from e

        prior = seen_ids.get(mr.round_id)
        if prior is not None:
            raise ValueError(
                f"{f}: duplicate round_id '{mr.round_id}' "
                f"(already defined by {prior}). round_id must be unique "
                f"within a mock_rounds/ directory because the baseline "
                f"digest is keyed on it."
            )
        seen_ids[mr.round_id] = f
        rounds.append(mr)

    return rounds


# ── SessionFileInjector (Stage 2.7.B) ──────────────────────────────────────

# Maximum cumulative bytes across all rounds' tool_result, on top of the
# per-round cap (MAX_TOOL_RESULT_BYTES). cc loads the entire session file
# on --resume, so a huge prefill slows everything down. See tech_design
# §4.9 R2.
MAX_SESSION_FILE_BYTES = 5_000_000  # 5 MB total

def _project_hash(sandbox_root: Path | str) -> str:
    """Derive cc's project-hash directory name from a sandbox path.

    cc stores per-cwd session files at
    `~/.claude/projects/<cwd_with_/_replaced_by_->/`. macOS pitfall: `/tmp`
    is a symlink to `/private/tmp`, so cc's hash is based on the
    *realpath* of the cwd, not the user-facing one. Spike Step 1 confirmed
    this empirically — see session-injection-spike-result.md §2.
    """
    real = str(Path(sandbox_root).resolve())
    return real.replace("/", "-")


def _claude_config_dir() -> Path:
    """Honour `CLAUDE_CONFIG_DIR` so codefuse-shipped cc (root at
    `~/.codefuse/engine/cc/`) finds forged sessions; falls back to the
    upstream `~/.claude/` layout when the env var is absent.
    """
    import os
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude"


def session_file_path(sandbox_root: Path | str, session_id: str) -> Path:
    """Where a forged session file lives.

    IMPORTANT: cc looks up resume targets by **session id** (it scans the
    project-hash dir for `<session_id>.jsonl`), so the filename MUST be
    `<session_id>.jsonl` verbatim — anything else surfaces as
    "No conversation found with session ID: …" at spawn time.

    The runner holds the session_id (returned by
    `SessionFileInjector.create_session_with_mock_history`) and passes it
    here for cleanup. `onecxt eval clean` walks the directory tree to
    find leftovers since there's no other discriminator on the filename.
    """
    return (
        _claude_config_dir()
        / "projects"
        / _project_hash(sandbox_root)
        / f"{session_id}.jsonl"
    )


class SessionFileInjector:
    """Forge a cc session jsonl file so `--resume <id>` loads it as history.

    The forged file contains, in order:
        1) user text message carrying the scenario's query
        2) for each MockRound: assistant(tool_use) + user(tool_result)

    cc reads this as "user asked X, assistant tool-called these N times
    and got these N results — now continue". The LLM has no motivation to
    re-invoke the already-completed tools, so the mocked tool_result
    values are treated as authoritative. See tech_design.md §4.

    Schema target: cc CLI 2.1.156 (spike-validated). The version is
    surfaced via `cc_version` (written into every message's `version`
    field) so future cc upgrades can pin via scenario.session_inject.
    schema_version + a runner-level mismatch warning (Stage 2.7.E).
    """

    def __init__(
        self,
        sandbox_root: Path | str,
        cc_version: str,
        requested_model: str,
    ):
        self.cwd = str(Path(sandbox_root).resolve())  # realpath, see _project_hash
        self.project_hash = _project_hash(sandbox_root)
        self.session_dir = _claude_config_dir() / "projects" / self.project_hash
        self.cc_version = cc_version
        self.requested_model = requested_model

    # ── public API ──

    def create_session_with_mock_history(
        self,
        user_input: str,
        mock_rounds: list[MockRound],
        run_id: str,
        *,
        final_assistant_text: Optional[str] = None,
    ) -> str:
        """Forge the session file. Returns the session_id for `--resume <id>`.

        Side effects:
            - mkdir -p `~/.claude/projects/<hash>/`
            - write `~/.claude/projects/<hash>/onecxt-eval-<run_id>.jsonl`

        R-5 治理 C (design §16.7.12): when `final_assistant_text` is given,
        append one trailing `assistant` text message with
        `stop_reason: end_turn` after all rounds. Without it the last
        forged event is a `user.tool_result` and cc, on resume, decides
        "the previous turn never produced an assistant final answer, I
        should continue". That continuation is the R-5 hot spot — cc
        starts fresh tool calls outside the mock range. With a
        `end_turn` terminator, cc sees a complete prior turn and is far
        more likely to acknowledge & summarize rather than re-do work.
        """
        # Pre-flight: total tool_result size (per-round cap was enforced by
        # MockRound.tool_result_size; this catches the additive case).
        total = sum(
            len(self._serialize_tool_result(r.tool_result).encode("utf-8"))
            for r in mock_rounds
        )
        if total > MAX_SESSION_FILE_BYTES:
            raise ValueError(
                f"forged session would carry {total} bytes of tool_result "
                f"across {len(mock_rounds)} rounds; cumulative cap is "
                f"{MAX_SESSION_FILE_BYTES} bytes. Trim fixtures (drop "
                f"irrelevant fields / keep only Top-N entries)."
            )

        self.session_dir.mkdir(parents=True, exist_ok=True)
        session_id = str(uuid_lib.uuid4())
        # MUST be `<session_id>.jsonl` — cc resolves --resume by scanning
        # for this exact filename. See session_file_path() docstring.
        # The `run_id` arg is kept for cleanup-side bookkeeping only.
        out_path = self.session_dir / f"{session_id}.jsonl"

        # Timestamps are ordered, leaving 1s gaps between messages. Anchor
        # 60s × rounds in the past so the whole sequence lands strictly
        # before "now" — matches what cc would write for a real run.
        t = datetime.now(timezone.utc) - timedelta(seconds=60 * max(len(mock_rounds), 1))
        prompt_id = str(uuid_lib.uuid4())
        user_uuid = str(uuid_lib.uuid4())

        msgs: list[dict[str, Any]] = []

        # 1) first user message: the scenario query (only written once;
        # subsequent rounds chain via parentUuid).
        msgs.append(self._user_text_message(
            content=user_input,
            uuid=user_uuid,
            parent_uuid=None,
            prompt_id=prompt_id,
            session_id=session_id,
            ts=t,
        ))
        last_uuid = user_uuid

        # 2) per round: assistant(tool_use) + user(tool_result)
        for mr in mock_rounds:
            t += timedelta(seconds=1)
            asst_uuid = str(uuid_lib.uuid4())
            # tool_use_id mirrors cc's format `toolu_vrtx_<...>`; the
            # exact prefix isn't load-bearing — what matters is the same id
            # appearing on both the assistant tool_use and the user
            # tool_result that follows.
            tool_use_id = f"toolu_vrtx_inj{uuid_lib.uuid4().hex[:20]}"

            msgs.append(self._assistant_tool_use_message(
                thinking=mr.assistant_thinking,
                tool_name=mr.tool_name,
                tool_input=mr.tool_input,
                tool_use_id=tool_use_id,
                uuid=asst_uuid,
                parent_uuid=last_uuid,
                session_id=session_id,
                ts=t,
            ))
            last_uuid = asst_uuid

            t += timedelta(seconds=1)
            tool_result_uuid = str(uuid_lib.uuid4())
            msgs.append(self._user_tool_result_message(
                tool_use_id=tool_use_id,
                content=self._serialize_tool_result(mr.tool_result),
                source_assistant_uuid=asst_uuid,
                uuid=tool_result_uuid,
                parent_uuid=last_uuid,
                prompt_id=prompt_id,
                session_id=session_id,
                ts=t,
            ))
            last_uuid = tool_result_uuid

        # R-5 治理 C: trailing assistant text + end_turn so cc resume
        # sees a complete prior turn, not an in-progress one.
        if final_assistant_text and final_assistant_text.strip():
            t += timedelta(seconds=1)
            final_asst_uuid = str(uuid_lib.uuid4())
            msgs.append(self._assistant_final_text_message(
                text=final_assistant_text,
                uuid=final_asst_uuid,
                parent_uuid=last_uuid,
                session_id=session_id,
                ts=t,
            ))
            last_uuid = final_asst_uuid

        with open(out_path, "w", encoding="utf-8") as f:
            for m in msgs:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

        return session_id

    # ── internal helpers ──

    @staticmethod
    def _serialize_tool_result(value: str | dict[str, Any] | list[Any]) -> str:
        """cc's tool_result.content is always a string. Dict/list go via JSON."""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _ts(ts: datetime) -> str:
        """ISO-8601 with millisecond precision, matching cc's writeback."""
        return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z"

    def _base_fields(self, session_id: str) -> dict[str, Any]:
        """Fields shared across all forged messages (cc 2.1.156 schema)."""
        return {
            "isSidechain": False,
            "userType": "external",
            "entrypoint": "sdk-cli",  # `-p` mode triggers SDK entry; see spike §4
            "cwd": self.cwd,
            "sessionId": session_id,
            "version": self.cc_version,
            "gitBranch": "HEAD",  # sandbox has no branch
        }

    def _user_text_message(
        self,
        content: str,
        uuid: str,
        parent_uuid: str | None,
        prompt_id: str,
        session_id: str,
        ts: datetime,
    ) -> dict[str, Any]:
        return {
            **self._base_fields(session_id),
            "parentUuid": parent_uuid,
            "promptId": prompt_id,
            "type": "user",
            "message": {"role": "user", "content": content},
            "uuid": uuid,
            "timestamp": self._ts(ts),
            "permissionMode": "bypassPermissions",
        }

    def _assistant_tool_use_message(
        self,
        thinking: str,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str,
        uuid: str,
        parent_uuid: str,
        session_id: str,
        ts: datetime,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if thinking:
            # cc real-trace puts thinking as a leading text block alongside
            # tool_use. We only include it when non-empty to avoid an
            # awkward empty-text block in the forged file.
            content.append({"type": "text", "text": thinking})
        content.append({
            "type": "tool_use",
            "id": tool_use_id,
            "name": tool_name,
            "input": tool_input,
        })
        return {
            **self._base_fields(session_id),
            "parentUuid": parent_uuid,
            "message": {
                "model": self.requested_model,
                "id": f"msg_vrtx_inj{uuid_lib.uuid4().hex[:20]}",
                "type": "message",
                "role": "assistant",
                "content": content,
                "stop_reason": "tool_use",
                "stop_sequence": None,
                "stop_details": None,
                "usage": _stub_usage(),
            },
            "type": "assistant",
            "uuid": uuid,
            "timestamp": self._ts(ts),
        }

    def _assistant_final_text_message(
        self,
        text: str,
        uuid: str,
        parent_uuid: str,
        session_id: str,
        ts: datetime,
    ) -> dict[str, Any]:
        """R-5 治理 C: closing assistant text + end_turn.

        Different from `_assistant_tool_use_message` in three ways:
        - `content` is a single text block, no tool_use
        - `stop_reason` is "end_turn" (not "tool_use") — this is the
          signal cc reads to decide "prior turn complete vs ongoing"
        - no tool_use_id bookkeeping
        """
        return {
            **self._base_fields(session_id),
            "parentUuid": parent_uuid,
            "message": {
                "model": self.requested_model,
                "id": f"msg_vrtx_inj{uuid_lib.uuid4().hex[:20]}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "stop_details": None,
                "usage": _stub_usage(),
            },
            "type": "assistant",
            "uuid": uuid,
            "timestamp": self._ts(ts),
        }

    def _user_tool_result_message(
        self,
        tool_use_id: str,
        content: str,
        source_assistant_uuid: str,
        uuid: str,
        parent_uuid: str,
        prompt_id: str,
        session_id: str,
        ts: datetime,
    ) -> dict[str, Any]:
        return {
            **self._base_fields(session_id),
            "parentUuid": parent_uuid,
            "promptId": prompt_id,
            "type": "user",
            "message": {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "content": content,
                    "is_error": False,
                    "tool_use_id": tool_use_id,
                }],
            },
            "uuid": uuid,
            "timestamp": self._ts(ts),
            "toolUseResult": content,
            "sourceToolAssistantUUID": source_assistant_uuid,
        }


def _stub_usage() -> dict[str, Any]:
    """Plausible-looking usage block. cc 2.1.156 requires the full shape;
    exact numbers don't matter for prefill semantics. See spike §4 table."""
    return {
        "input_tokens": 1,
        "cache_creation_input_tokens": 1,
        "cache_read_input_tokens": 0,
        "output_tokens": 1,
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        "service_tier": "standard",
        "cache_creation": {
            "ephemeral_1h_input_tokens": 0,
            "ephemeral_5m_input_tokens": 1,
        },
        "inference_geo": "",
        "iterations": [],
        "speed": "standard",
    }


# ── detect_cc_version (Stage 2.7.B.2) ──────────────────────────────────────


_CC_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


@functools.lru_cache(maxsize=1)
def detect_cc_version() -> str:
    """Return the live `claude --version` string, e.g. '2.1.156'.

    Used by the runner to (a) populate `cc_version` in forged session
    messages and (b) compare against scenario.session_inject.schema_version
    for the mismatch warning.

    Cached process-wide via lru_cache; tests that need a fresh probe must
    call `detect_cc_version.cache_clear()`.

    Returns 'unknown' if `claude` is not on PATH or the version line can't
    be parsed — the runner treats 'unknown' as a soft warning rather than
    a hard fail (a missing cc would also break the spawn itself, so the
    error surfaces there with a clearer message).
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "unknown"
    raw = (result.stdout or result.stderr or "").strip()
    m = _CC_VERSION_RE.search(raw)
    return m.group(1) if m else "unknown"
