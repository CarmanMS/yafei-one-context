# 交付说明 — MATH1027 2025–2026-2 期末 B 卷

关联：`spec.md`  
**交付状态：未完成（in_progress）** — pilot 已出，待用户验收后扩整卷。

## 交付范围（目标）

| 文件 | 路径 | 当前状态 |
|------|------|----------|
| B 卷 pilot | `…/2025-2026-2-MATH1027-final-B-paper-inline-omml-pilot.docx` | **已生成**（Q1+计算Q4）；待用户验收 |
| B 卷试卷定稿 | `…/2025-2026-2-MATH1027-final-B-paper.docx` | 旧草稿，**勿用** |
| B 卷答案 | `…/2025-2026-2-MATH1027-final-B-answer.docx` | **未同步**；含 A OLE 残留 |
| B 卷 PDF | `…/2025-2026-2-MATH1027-final-B-paper.pdf` | **未生成** |

## 结论摘要

- **根因**：WPS OLE 公式改不到；段后 OMML 版式不对；Word COM 卡死。
- **可行路径**：**行内 OMML** + `skills/docx-mcp/lib/`（详见 `tech_design.md`「核心心得」）。

## 内容真源

- B 卷 20 题换题方案：**`tech_design.md`**（接手人以此为准，不以当前 docx 为准）

## 回滚

- A 卷定稿未改动：`…-final-A-paper.docx`、`…-final-A-answer.docx`
- 可删除或覆盖当前 B 文件，从 A 重新复制出卷

## 给接手人的入口

1. **`tech_design.md`** — 换题表 + **结论与核心心得**
2. **`handoff.md`** — 当前状态与下一步
3. **`issue_checklist.md`** — 问题与文件清单
4. **`skills/docx-mcp/SKILL.md`** §D — 行内 OMML 复用手册

## 自动化入口

- 库：`skills/docx-mcp/lib/inline_omml.py`
- 示例补丁：`skills/docx-mcp/references/inline-omml-patches.example.json`
