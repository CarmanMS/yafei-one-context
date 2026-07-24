# Standards

Tool-neutral engineering conventions and policies for `one-context`.

## Files

| File | Scope |
|------|-------|
| `agent-framework.md` | 智能体定义规范 — Agent schema, role enum, adapter contract |
| `one-context-conventions.md` | 项目约定 — Canonical sources, adapter model, validation |
| `video-voiceover-script-conventions.md` | 口播稿 — 开场钩子（含悬念/排比否定式）后紧接固定关注句（逐字）；与 `01-script.md` 配合 |
| `content-pipeline-tts-routing.md` | content-pipeline 立项 — **默认** `volc-podcast-tts` action=0、`00-podcast-source.md`、WAV+SRT 真源；action=3 须 `override_reason` |
| `dev-env-traps.md` | 开发环境陷阱 — 易被误判为代码 bug 的现象（如 Remotion + SOCKS 代理 AbortError） |

## What belongs here

- Coding conventions and repository layout policies
- Documentation standards and testing expectations
- Safety, write-boundary, and data-handling policies
- Schema definitions and interface contracts

## What does NOT belong here

- Architecture analysis or source-code walkthroughs → `references/`
- Diagram samples and visual design guides → `references/`
- Step-by-step operating procedures → `playbooks/`

Add links to new standards in the table above when creating a file.