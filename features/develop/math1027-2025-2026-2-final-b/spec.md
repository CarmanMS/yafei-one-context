---
id: math1027-2025-2026-2-final-b
title: MATH1027 2025–2026-2 期末 B 卷出卷
status: in_progress
category: develop
primary_repo_id: ""
owner: ""
updated: "2026-05-30"
---

# 概述

高等数学 B（二）（MATH1027）2025–2026 学年第二学期期末考试 **B 卷**出卷。A 卷已定稿，需在 **保留学院 Word 版式** 的前提下，基于 A 卷复制改写，产出 B 卷试卷与参考答案。

# 目标与非目标

## 目标

- 产出 `2025-2026-2-MATH1027-final-B-paper.docx` 与 `2025-2026-2-MATH1027-final-B-answer.docx`
- 卷面结构与 A 卷一致：选择 5×3、填空 5×3、计算 7×7、综合 3×7，满分 100
- **每道题与 A 卷题干不同**（可换函数/数字/参数/表述）；约 **35%** 题目换到 **相邻考点**，其余同考点平行变题
- 难度与 A 卷相当；页眉、装订线、分值表等版式与 A 一致

## 非目标

- 不重排 LaTeX/PDF 整卷（不走 `pdf-exam-pipeline` 作为主路径）
- 不修改 A 卷定稿
- 不在本需求内完成印刷/教务系统上传

# 用户与场景

- **用户**：任课教师，需 A/B 卷防作弊且难度可比
- **场景**：期末考试前交付教务处；阅卷参照 B 卷答案 docx

# 验收标准

- [ ] B 卷 `paper.docx` 页眉「试卷类型」为 **B**，其余版式元素与 A 同型
- [ ] 20 小题 **无一与 A 卷完全相同**（含选择题 **选项公式**，非仅题干中文）
- [ ] 至少 7 题（约 35%）考查点与 A 卷对应题 **相邻替换**（见 `tech_design.md` 换题对照表）
- [ ] 题量、分值、大题顺序与 A 一致
- [ ] B 卷 `answer.docx` 与 B 卷题干一一对应，含选择答案表与主要步骤分值标注
- [ ] 在 Word/WPS 中打开无严重乱码；公式为可接受的编辑器格式（非 A 卷残留 OLE）

> **2026-05-30**：pilot **未通过**（用户目视仍为 A 卷；段落 index 错误）。当前路径：修正 `inline_omml` 段落定位后重做 pilot。详见 `tech_design.md`「pilot 失败详情」。

# 实现落点（必填）

- **仓库 id**（`meta/repos.yaml`）：无独立子仓；资产在 one-context 主库 `repos/teaches/`
- **分支 / PR**：—（本地教学资产，按需提交 one-context）
- **主要路径或模块**：
  - A 卷母版：`repos/teaches/courses/MATH1027/exams/2025-2026-2/2025-2026-2-MATH1027-final-A-paper.docx`
  - A 卷答案：`…/2025-2026-2-MATH1027-final-A-answer.docx`
  - B 卷产出：`…/2025-2026-2-MATH1027-final-B-paper.docx`、`…/2025-2026-2-MATH1027-final-B-answer.docx`
  - 课程元数据：`repos/teaches/courses/MATH1027/course.yaml`
  - 编写计划：`features/develop/math1027-2025-2026-2-final-b/tech_design.md`
  - 自动化：`skills/docx-mcp/lib/`（行内 OMML）；pilot 见 `tech_design.md`「核心心得」

# 关联

- **Workspace**：example-workspace（如适用）
- **其他需求**：
  - `features/research/pdf-math-exam-to-latex-skill-survey/` — PDF/LaTeX 管线调研（非本次主路径）
  - Skill：`skills/docx-mcp/` — Word 改题流程

# 开放问题

- pilot 公式观感是否被用户接受（Word COM OMath vs 学院 WPS OLE）
- B 卷定稿后是否需导出 PDF（`convert_to_pdf`）一并归档
- 是否在 `meta/repos.yaml` 登记 `repos/teaches` 以便 smart-commit 分类
- 接手人：从现 `B-paper.docx` 修，还是从 A 重新复制更干净？
