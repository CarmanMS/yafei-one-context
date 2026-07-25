# AGENTS.md — AI Tool Usage Guide

This file provides guidance for AI coding tools (Cursor, Claude Code, Codex, etc.) working in this repository.

## Workspace Layout

- **`packages/one-context/`**: installable Python package; CLI `onecxt` / module `one_context` — **implement CLI changes here**; usage in `packages/one-context/README.md`
- **`meta/repos.yaml`**: repository registry (URL, local path, `id` / `alias`, description)
- **`meta/workspaces.yaml`**: task- or theme-oriented workspace definitions
- **`meta/profiles.yaml`**: shared AI/runtime profiles
- **`knowledge/`**: personal Obsidian vault (科研/教学/家庭), git submodule; layout in `knowledge/README.md`. **NOT an agent-guidance layer anymore** (restructured 2026-07-25; old standards/playbooks/prompts live in submodule git history `267c959`)
- **`skills/`**: cross-tool executable helpers (e.g. HTML slides → MP4); see `skills/README.md`
- **`features/`**: umbrella-level feature specs; see `features/README.md` and `features/INDEX.md`
- **`repos/reference/`**: upstream reference repos (declared in `meta/repos.yaml` with `category: reference`, not committed); same sync model as other `repos/` categories
- **`docs/`**: architecture docs and contributor templates

## Skill routing (mandatory)

When the user’s request matches a workflow below, **do not** answer with ad‑hoc system commands only. **Read the listed `SKILL.md` first**, then follow it (including running scripts from this repo).

| User intent (examples) | Authoritative entry |
|------------------------|---------------------|
| HTML slides + narration → MP4 / 生成视频 / 口播视频 | `skills/html-video-from-slides/SKILL.md` — **WAV 真源五步**见同目录 `references/WAV-FIRST-WORKFLOW.md` |
| 幻灯空白多、字/图太小、presentation 版式、`fill-deck`、全屏 HTML 幻灯排版 | `skills/html-deck-layout/SKILL.md` |
| Selective merge to `main` (docs/framework/skills vs business assets) | `skills/merge-to-main/SKILL.md` |
| 火山播客 / podcasttts / 双人播客 WebSocket v3 / 长文本/URL → 播客音频 | `skills/volc-podcast-tts/SKILL.md` |
| `/gitsync`, git sync, pull remote, sync with origin, 同步远程, 拉取不丢本地 | `skills/gitsync/SKILL.md` |
| 口播稿与幻灯一致性、讲稿校对 presentation、script deck audit、口播要点是否在画面上 | `skills/script-deck-audit/SKILL.md` — `node skills/script-deck-audit/cli.js audit --project <production>` |
| PPT 样式循环矫正、幻灯空白太多、纯文字无图、元素重叠、fill-deck 矫正 | `skills/ppt-style-loop-correct/SKILL.md` — `node skills/ppt-style-loop-correct/cli.js audit-dom --project <production>` |
| 新建 content-pipeline / 中视频 spec / 口播立项 | `features/_template/spec-content-pipeline.md` — **默认 action=0**，勿因双人讲稿自动选 action=3 <!-- TODO(skill重构): 原 knowledge/standards/content-pipeline-tts-routing.md 已随 knowledge 重构删除，规范待迁入 skills/ --> |
| AI 生图封面 / cover-prompt / 写 `production/cover-prompt.md` | `skills/cover-prompt/SKILL.md` — **Step 0 默认极简**（2 行标题）；信息密度须用户明确授权；勿把 Remotion Scene/00-structure 密度搬进缩略图 |
| 封面 Lottie / cover.html 动画主视觉 / 代替 SVG 图形 | `skills/html-lottie-cover/SKILL.md` — `decoLottie` + `vendor/`；截图 `node cli.js cover --project <production>` |

Until the matching `SKILL.md` has been read, treat generic snippets (e.g. only `Get-PSDrive`) as **insufficient** for those intents.

## Features / Umbrella Requirements

Cross-repository or product-level requirement documents live in **`features/`**. Before creating, editing, or implementing such requirements, read **`features/README.md`**; index table at **`features/INDEX.md`**. When linking code to features, use the repository **`id`** from `meta/repos.yaml` (do not guess paths).

<!-- TODO(skill重构): 原 playbook knowledge/playbooks/add-umbrella-feature.md 已随 knowledge 重构删除（可从子仓历史 267c959 找回），待迁入 skills/ 或 docs/ -->

## Default output style (minimal / 文言极简)

Unless the user **explicitly** asks for a different style, length, format, or language, agents should default to **minimal output**: modern wording, shortest useful phrasing, no pleasantries, do not restate the question—**answer first**. This reduces output tokens and matches `meta/profiles.yaml` profile **`default-coding`** (`output_style.tone: minimal`).

**Overrides:** Phrases such as “详细说明”, “展开讲”, “tutorial 口吻”, “step by step”, “in English”, “用表格”, etc. take precedence for that request.

**Lighter default:** Profile **`default-coding-lighter`** uses `tone: concise` (via mixin `output-concise`) when minimal is too aggressive for a workspace.

Canonical machine-readable policy: `meta/profiles.yaml`; tool-specific text is emitted by adapters (`one_context.adapters`).

## Conventions

- When answering questions or editing code in this umbrella repo, use the manifests above; do not guess remotes or paths.
- For deeper structure, see `docs/architecture.md`.
- After editing manifests, validate with: `onecxt doctor` (or `python -m one_context doctor`)
- Do not run destructive commands without asking.
- **Obsidian vault 笔记（`knowledge/**`）只能经 Obsidian Local REST API 访问**（`curl → https://127.0.0.1:27124`）。**禁止**用 `Read`/`Write`/`Edit`/`Grep` 或直接文件系统操作去读改 `knowledge/` 下的笔记文件——直读直写会绕过 Obsidian 索引导致脱节。唯一允许直接文件工具修改的是 skill 自身定义文件（`skills/obsidian-knowledge/` 下的 `SKILL.md`/`playbooks/*`/`references/*`/`api-key.txt`）。

## Agent Templates

The `docs/templates/` directory contains template files (SOUL.md, USER.md, etc.) that demonstrate how to configure personal AI agent behavior. These are **examples**, not active configuration.
