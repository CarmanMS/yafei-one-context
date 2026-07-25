"""Parse ``stream-json.jsonl`` into a flat event sequence (Stage 2.5.1.c).

The Claude Code provider streams each model turn as a series of JSONL
lines (``type: assistant`` with thinking/text/tool_use content blocks,
``type: user`` with tool_result blocks, ``type: system`` for init,
``type: result`` for final). This module flattens that into a single
ordered list of events suitable for rendering an execution timeline in
``report.html`` (think → tool_use → tool_result → text alternation).

Schema (each list entry):
    {
      "idx":  <1-based int>,
      "kind": "sys.init" | "think" | "text" | "tool_use" | "tool_result" | "result",
      # kind-specific:
      "preview": <one-line truncated summary>,
      "full":    <complete text, when applicable>,
      "size":    <chars, when applicable>,
      # tool_use only:
      "tool":         <tool name>,
      "input":        <dict, with Write.content replaced by a placeholder>,
      "tool_use_id":  <str>,
      # tool_result only:
      "tool_use_id":  <str>,
      "is_error":     <bool>,
      # sys.init only:
      "meta": { "model": ..., "cwd": ..., "tools": [...] },
      # result only:
      "cost_usd": <float>,
    }

Why we strip ``Write.content`` from tool_use ``input``: the same bytes
are already preserved in ``__reports/<runId>/artifacts/`` and would
otherwise duplicate ~9 KB in run.json for every Write call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PREVIEW_LEN = 160
WRITE_CONTENT_PLACEHOLDER = "<{n} chars — see artifact>"


def _one_line(s: str, limit: int = PREVIEW_LEN) -> str:
    s = (s or "").replace("\n", " ").replace("\r", " ")
    return s[:limit]


def _tool_result_text(content: Any) -> str:
    """Anthropic tool_result content can be str OR list of blocks."""
    if isinstance(content, list):
        parts: list[str] = []
        for x in content:
            if isinstance(x, dict):
                parts.append(x.get("text", "") or "")
            else:
                parts.append(str(x))
        return "".join(parts)
    if isinstance(content, str):
        return content
    return str(content) if content is not None else ""


def parse_stream_json(path: Path) -> list[dict[str, Any]]:
    """Read ``stream-json.jsonl`` and return the flat event list.

    A missing or empty file yields ``[]`` (callers should not crash when
    provider failed before producing any events).

    Stage 2.5.3: each parsed line may carry a ``_t`` field (epoch ms)
    injected by ``evals/providers/claude-code.js``. We propagate it as
    ``t_ms`` on every flat event derived from that line, plus a
    ``t_offset_ms`` relative to the first event so the UI can render a
    real wall-time Gantt without doing arithmetic in templates.
    Lines from older providers without ``_t`` get ``t_ms = None``.
    """
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue

            t_ms = e.get("_t") if isinstance(e.get("_t"), (int, float)) else None
            before = len(events)
            t = e.get("type")
            if t == "system" and e.get("subtype") == "init":
                events.append({
                    "kind": "sys.init",
                    "meta": {
                        "model": e.get("model"),
                        "cwd":   e.get("cwd"),
                        "tools": e.get("tools", []),
                    },
                    "preview": f"model={e.get('model')} · {len(e.get('tools', []))} tools",
                })

            elif t == "assistant":
                for b in (e.get("message") or {}).get("content") or []:
                    bt = b.get("type")
                    if bt == "thinking":
                        txt = b.get("thinking", "") or ""
                        events.append({
                            "kind": "think",
                            "size": len(txt),
                            "preview": _one_line(txt),
                            "full": txt,
                        })
                    elif bt == "text":
                        txt = b.get("text", "") or ""
                        events.append({
                            "kind": "text",
                            "size": len(txt),
                            "preview": _one_line(txt),
                            "full": txt,
                        })
                    elif bt == "tool_use":
                        name = b.get("name")
                        inp = b.get("input") or {}
                        # Strip Write/Edit content (already in artifacts/)
                        display_input: dict[str, Any] = {}
                        for k, v in inp.items():
                            if (
                                name in ("Write", "Edit")
                                and k == "content"
                                and isinstance(v, str)
                            ):
                                display_input[k] = WRITE_CONTENT_PLACEHOLDER.format(n=len(v))
                            else:
                                display_input[k] = v
                        if name == "Bash":
                            preview = _one_line(inp.get("command") or "")
                        elif name in ("Read", "Write", "Edit"):
                            preview = _one_line(inp.get("file_path") or "")
                        else:
                            preview = _one_line(
                                json.dumps(display_input, ensure_ascii=False)
                            )
                        events.append({
                            "kind": "tool_use",
                            "tool": name,
                            "preview": preview,
                            "input": display_input,
                            "tool_use_id": b.get("id"),
                        })

            elif t == "user":
                for b in (e.get("message") or {}).get("content") or []:
                    if b.get("type") == "tool_result":
                        txt = _tool_result_text(b.get("content"))
                        events.append({
                            "kind": "tool_result",
                            "size": len(txt),
                            "preview": _one_line(txt),
                            "full": txt,
                            "tool_use_id": b.get("tool_use_id"),
                            "is_error": bool(b.get("is_error")),
                        })

            elif t == "result":
                events.append({
                    "kind": "result",
                    "cost_usd": e.get("total_cost_usd"),
                    "preview": _one_line(e.get("result") or ""),
                })

            # propagate per-line timestamp to every event derived from it
            for ev in events[before:]:
                ev["t_ms"] = t_ms

    # add 1-based idx + t_offset_ms relative to first timestamped event
    base_t = next((ev["t_ms"] for ev in events if ev.get("t_ms") is not None), None)
    for i, ev in enumerate(events):
        ev["idx"] = i + 1
        ev["t_offset_ms"] = (ev["t_ms"] - base_t) if (base_t is not None and ev.get("t_ms") is not None) else None
    return events
