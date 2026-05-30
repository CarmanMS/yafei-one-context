---
id: pdf-math-exam-to-latex-skill-survey
title: 数学试卷 PDF → LaTeX 能力调研（Skill / 工具 / 开源方案）
status: in_progress
# tech_design.md + pilot/ MVP 已建；PDF 导出待本机安装 xelatex + MinerU 实测
category: research
primary_repo_id: one-context
owner: user
updated: 2026-05-25
---

# 概述

**业务目标（用户 2026-05-25 澄清）**：要能 **出新考题**，且 **版式参考现有学校期末卷 PDF**；中间产物必须 **可编辑**，并能 **再导出为 PDF**（可逆排版链路）。

因此本调研的核心不是「存档级 PDF 复刻」，而是：

1. **版式模板**：从样卷 PDF 抽出或复刻页眉、题型结构、选择题版式、分值栏等（可人工微调）。
2. **可编辑源稿**：教师/Agent 改题干、换数、增删题——推荐以 **LaTeX（`ctex` + `exam`）** 为主源，辅以结构化题库（JSON/YAML）。
3. **回导 PDF**：`xelatex` / `latexmk` 一键出卷，版式与样卷尽量一致。

需要把 **数学试卷类 PDF**（含大量公式、题号、选项、配图、可能含中文）转为上述可编辑源稿；用于 **出题、组卷、教研改编**，并与 `math-teacher-ai-platform` 的「题目集 → 导出 PDF」衔接。

本需求 **不先实现完整产品管线**，而是系统调研：是否存在可复用的 **Agent Skill**、**CLI/库**、**商业 API**，以及其针对 **数学试卷 + 可编辑 + PDF 回导** 的适用性与局限。

本仓 **尚无** 内置 `pdf-to-latex` skill；仅有文档转换类能力（如 `knowledge/playbooks/use-microsoft-markitdown.md` 的 PDF→Markdown、用户侧 `pdf-to-markdown` skill）——**Markdown 不等于 LaTeX**，数学公式与版式保真需单独评估。

# 目标与非目标

## 目标

1. **盘点候选方案**（≥15 条有效条目），来源包括：
   - GitHub 开源项目（含 `SKILL.md` / Agent Skills 仓库）
   - 各 Agent 平台的 skill 市场或 awesome 列表
   - 学术/工业向工具（OCR+公式、PDF 结构化、整页转 TeX）
2. **按统一维度对比**，重点面向 **数学试卷 PDF**（非普通论文、非纯文字扫描件）。
3. **给出推荐分级**：可直接用 / 需二次开发 / 仅作参考 / 不推荐。
4. **产出调研报告**（见 `deliver.md` 或本目录 `survey-report.md`），含：
   - 对比表（工具中立，附链接与许可证）
   - 1～2 个「建议试点」及试点条件（样张类型、验收指标）
5. 若存在 **可纳入 one-context `skills/`** 的成熟 Skill，在报告中单独列出「入库候选」及适配成本。

## 非目标

- 本阶段 **不** 编写完整 PDF→LaTeX 转换实现。
- 本阶段 **不** 承诺任意扫描版试卷都能自动得到可编译 `.tex`（行业普遍需人工校对）。
- 本阶段 **不** 将调研范围扩大到通用「PDF 转 Word」除非与 LaTeX/公式强相关。
- 本阶段 **不** 采购或长期订阅商业服务（可记录试用方式与报价线索）。

# 用户与场景

| 角色 | 场景 |
|------|------|
| 教研 / 题库运营 | 纸质或电子版试卷入库，需 LaTeX 或接近 LaTeX 的源稿 |
| 内容管线 / Agent 工作流 | 希望在 Cursor/Claude 中用 **Skill** 一键「试卷 PDF → .tex」 |
| 数学教师 AI 产品 | 与 `features/products/math-teacher-ai-platform/` 的出题、排版链路衔接 |

**样张类型（调研时需分别标注表现）**：

- A. 电子版 PDF（文字可选中、公式为矢量或嵌入字体）
- B. 扫描版 PDF（拍照/扫描，需 OCR + 公式识别）
- C. 中英混排 + 题号/分值/选项排版
- D. 含几何图、函数图像、填涂答题卡等非文字块

# 调研维度（对比表列）

| 维度 | 说明 |
|------|------|
| 名称与类型 | Skill / CLI / API / 桌面应用 / 在线服务 |
| 来源与许可 | URL、开源协议、是否可离线 |
| 输出形态 | 直接 `.tex` / 中间 Markdown+MathJax / 仅公式片段 |
| 公式保真 | 分数、根号、矩阵、对齐环境、编号是否可恢复 |
| 版式结构 | 题号、小题、选项 ABCD、分页、页眉页脚 |
| 中文与字体 | 简体试卷、标点、数学符号混排 |
| 配图处理 | 提取为 `\includegraphics` 还是忽略/占位 |
| 可编译性 | 输出是否接近「一次 `xelatex` 通过」 |
| Agent 集成 | 是否有 `SKILL.md`、是否适合 one-context skill 范式 |
| 成本与依赖 | GPU、商业 key、Windows 友好度 |
| 数学试卷实测 | 未测 / 部分 / 有公开样例（调研时填） |

# 验收标准

- [ ] `survey-report.md`（或 `deliver.md` 正文）包含 **≥15** 条有来源链接的候选方案。
- [ ] 每条候选至少覆盖上表 **公式保真、输出形态、Agent 集成、数学试卷实测** 四列。
- [ ] 明确区分 **「真·PDF→LaTeX」** 与 **「PDF→Markdown/HTML 再手工转 LaTeX」** 两类，避免误报。
- [ ] 给出 **TOP 3 推荐**（各一句话理由 + 主要风险）。
- [ ] 若存在 Skill 形态方案，列出 **是否已有 `SKILL.md`**、仓库 star/最近更新（大致即可）。
- [ ] 与 `math-teacher-ai-platform` 的衔接建议（1 段，可选实现路径）。
- [ ] 报告结论中说明：**是否建议在 one-context 新建 `skills/pdf-to-latex`（或等价名）**。

# 实现落点（必填）

- **仓库 id**（`meta/repos.yaml`）: `one-context`（调研产物落在本 feature 目录；若后续立项 skill 则 `skills/<name>/`）
- **分支 / PR**: 在默认分支提交 `features/research/pdf-math-exam-to-latex-skill-survey/**`
- **主要路径或模块**:
  - `features/research/pdf-math-exam-to-latex-skill-survey/spec.md` — 本需求
  - `features/research/pdf-math-exam-to-latex-skill-survey/survey-report.md` — 调研报告（执行阶段创建）
  - `features/research/pdf-math-exam-to-latex-skill-survey/samples/` — 可选：脱敏样张说明（**勿提交** 受版权保护的完整试卷 PDF 入 Git）

# 关联

- **Workspace**（`meta/workspaces.yaml` id，如有）: —
- **其他需求目录**:
  - `features/products/math-teacher-ai-platform/` — 潜在下游产品
  - `knowledge/playbooks/use-microsoft-markitdown.md` — PDF→Markdown，对照参考
- **本仓已有 skills（相关但非 LaTeX）**:
  - 用户环境：`pdf-to-markdown`（Claude/Cursor 个人 skill）— 调研时对比是否可链式转 LaTeX

# 调研种子清单（执行时扩展，非结论）

> 以下仅为 **检索起点**，正式报告须独立核实、补链接与实测备注。

**Skill / Agent 生态**

- GitHub 搜索：`pdf to latex skill`、`agent skill pdf latex`、`SKILL.md pdf latex`
- `anthropics/skills`、`agentskills` 规范仓库及社区 fork
- Cursor / Claude Code skills 目录（含 skills.sh、awesome 列表）

**开源 / 工具向（示例类别）**

- 公式 OCR：LaTeX-OCR / pix2tex、Mathpix 开源替代品、Nougat（偏论文）
- PDF 结构化：Marker、MinerU、pdf2json 类
- 转换链：Pandoc（通常非直接 PDF）、pdf2latex 类老旧工具
- 整页重建：InftyReader、Textract 类商业/学术工具（记许可证）

**评估时注意**

- 很多方案输出 **MathML / Unicode 数学** 而非可维护 `.tex` 源。
- 试卷 **分栏、装订线、答题框** 可能丢失，需在报告中单列「版式损失」说明。

# 开放问题（已部分由用户澄清）

| # | 问题 | 用户倾向（2026-05-25） |
|---|------|------------------------|
| 1 | 最终形态 | **可编辑 + 能再出 PDF**；参考现有 PDF 版式出题 |
| 2 | LaTeX 模板 | 待确认：是否接受 `exam` + `ctex` 类学校卷版式（推荐） |
| 3 | 校对比例 | 版式模板可一次人工定稿；**新题**由 AI/教师编辑，不必整卷 OCR |
| 4 | 离线 / 云 | 待确认 |
| 5 | 样张 | 已提供 2 份高数期末卷（Downloads，勿入库） |

# 验收标准（业务向，立项时追加）

- [ ] 存在 **可编辑源文件**（`.tex` 或等价）与 **样卷版式模板** 的对应关系说明
- [ ] 演示路径：**改 1 道题 → 重新编译 → PDF** 版式不破
- [ ] 与 `math-teacher-ai-platform` Phase 1「题目集导出 PDF」可对接
