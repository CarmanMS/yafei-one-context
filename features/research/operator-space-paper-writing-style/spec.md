---
id: operator-space-paper-writing-style
title: 算子空间论文表述规范（范本蒸馏 + Skill）
status: in_progress
category: research
primary_repo_id: paperwork
owner: ""
updated: "2026-05-05"
---

# 概述

在 one-context 中长期撰写 **算子空间（operator space）** 方向论文时，需要统一 **英文叙述语气与结构**：以本地存档的 LaTeX 范本 `revisedoperatorspace.tex`（与 Pisier / LMS 算子空间教材一脉）为主参照，同时约束 AI 辅助写作时的 **去「AI 味」** 与 **精简不啰嗦**。

本需求交付 **可检索的知识库条文** + **薄层 Skill 流程**（何时加载、检查清单），不把整本 `.tex` 全文搬进 `knowledge/`。

# 目标与非目标

## 目标

- 在 `knowledge/references/` 新增一篇 **写作规范**（kebab-case 英文名），包含：术语与符号习惯摘要、段落节奏偏好、常见句式类别（定义—命题—证明衔接）、**禁止的机翻/模型腔**列表、**精简**原则（删冗余从句、避免重复铺垫）。
- 在 `skills/<name>/SKILL.md` 新增薄 Skill：**起草/改写**算子空间论文自然段时必须先读该 knowledge 文件；输出前过一遍「去 AI 味 + 删冗」自检。
- 规范正文中 **显式指向** 范本路径：`repos/research/paperwork/archive/20201107/revisedoperatorspace.tex`（仅作本地参照；若日后该书有正式出版信息，在 knowledge 来源块中补充并可注明「叙述风格对齐该书修订稿」）。
- 完成后可选运行 `onecxt adapt`（或项目惯例的适配命令），使 Cursor / Claude Code 等侧出现对应 skill 规则（与现有 skill 管线一致）。

## 非目标

- 不代替期刊模板（AMS-Latex、期刊 `.cls` 等）与排版细节；Skill 只管 **自然语言层**。
- 不要求自动从 `.tex` 抽取全书；以 **人工蒸馏 + 必要时抽样摘抄（短引）** 为主，避免版权问题与大文件入库。
- 不绑定特定 LLM 产品名或专有 API。

# 用户与场景

- **作者**：用 AI 辅助写 introduction、remark、证明过渡句，但希望语气接近熟悉的教材/修订稿，且不像翻译腔或清单式 AI 作文。
- **触发**：用户提及「按算子空间表述规范写」「/operator-space-prose」或等价触发词时走 Skill。

# 验收标准

- [x] `knowledge/references/operator-space-paper-prose.md` 已创建，含来源信息块（图书 DOI + 本地 `.tex` 私用说明），**无原文摘录**。
- [x] `skills/operator-space-paper-prose/SKILL.md` 已创建（触发含「写算子空间论文」、同线程延续、必读 knowledge、自检）。
- [x] 与 `tech_design.md` 路径一致；`features/INDEX.md` 已登记。
- [x] 抽检指引与 CLI 校验：见 `test_report.md`；IDE 内两段式提示词待作者本地点一次确认。

# 实现落点（必填）

- **仓库 id**（`meta/repos.yaml`）：`paperwork`（`repos/research/paperwork`，远程 `CarmanMS/paperwork`）。
- **分支 / PR**：文档与 skill；按团队习惯开分支或直接 `main` 小步提交。
- **主要路径或模块**：
  - 任务追踪：`features/research/operator-space-paper-writing-style/`（本目录）。
  - 范本（只读参照）：`repos/research/paperwork/archive/20201107/revisedoperatorspace.tex`。
  - 计划产出：`knowledge/references/operator-space-paper-prose.md`（文件名可按 `tech_design.md` 最终裁定微调）。
  - 计划产出：`skills/operator-space-paper-prose/SKILL.md`（目录名与 adapt 生成物对齐）。

# 关联

- **Workspace**（`meta/workspaces.yaml` id，如有）：无。
- **其他需求目录**：`features/research/p-operator-space-injective-papers/`（同属算子空间写作与研究语境，可交叉引用）。

# 开放问题

（已决）来源块：图书 DOI + 本地 `.tex` 私用说明；无正文摘录。触发：含「写算子空间论文」及中英同类 phrase；**同对话后续修改默认沿用** Skill。产出语言：**英文**；范围：**全文含定理与证明**。
