---
id: agent-long-term-memory-content-ready
title: Agent 长期记忆如何选？阿里云选型指南
status: draft
category: content-pipeline
primary_repo_id: one-context
owner: 水猿
updated: "2026-05-29"
tts:
  engine: volc-podcast-tts
  action: 0
  authority: wav_srt
  override_reason: ""
render:
  stack: remotion-pipelines
---

# 概述

中视频深度解析（约 8–12min）：面向 AI 工程师与架构师，系统讲解 AI Agent 长期记忆的分层架构、Record & Retrieve 核心流程、主流存储方案对比，以及阿里云四套长期记忆方案的选型对比与实践建议。

> 本目录是 **共享评测 fixture（content-ready 进度截面）**，位于 `features/_evals/` 共享池。
> 当前被 `skills/cover-prompt/evals/mid-video/scenario.yaml` 引用。
> 不是真实在做的 feature；修改前请阅读同目录的 `FIXTURE_README.md`。

# 目标

- 让 cover-prompt skill 在该 feature 目录下生成 `production/cover-prompt.md`
- 主题与硬件/存储相关 → 期望走 **C · 主题实物微距** 背景类型
- 标题候选：「Agent 长期记忆如何选？」（行内英雄短语候选：「记得住」）

# 章节梗概

1. 为什么 Agent 需要长期记忆（无状态 LLM 的根本约束）
2. 短期 / 会话 / 长期三层记忆架构
3. 主流存储方案对比（向量数据库 / 知识图谱 / Markdown）
4. 主流框架对比（Mem0 / OpenViking / OpenClaw / Zep）
5. 阿里云四方案选型（百炼 API / RDS PG / PolarDB Mem0 / Polar Agent Memory）
