# 教学试卷 — docx-mcp 路径与改题约定

权威目录说明：`repos/teaches/README.md`。

## 根路径

```text
repos/teaches/courses/{COURSE_CODE}/exams/{AY}-{TERM}/
```

示例：

```text
repos/teaches/courses/MATH1027/exams/2025-2026-2/
├── 2025-2026-2-MATH1027-final-A-paper.docx
├── 2025-2026-2-MATH1027-final-A-answer.docx
├── 2025-2026-2-MATH1027-final-B-paper.docx
└── 2025-2026-2-MATH1027-final-B-key.docx    # 若本地命名用 key 表答案，以实际文件名为准
```

文件名模式：

```text
{学年}-{学期}-{课号}-{考试类型}-{试卷号}-{角色}.docx
```

| 角色 | 含义 |
|---|---|
| `paper` | 试卷正文 |
| `answer` / `key` | 参考答案（以目录内实际后缀为准） |

改题草稿：同目录追加后缀，如 `…-paper-q1-revised.docx`（**勿覆盖**定稿 `…-paper.docx`）。

## 课程元数据

每门课：`repos/teaches/courses/{CODE}/course.yaml`（中文名、学院、题型结构说明）。改卷面前可读一眼，避免分值/题量与课纲不符。

## 推荐改题流程（docx-mcp）

### 纯文字 / 无嵌入公式

```
1. open_document(…-paper.docx)
2. get_headings() / get_document_info()     → 确认大题结构
3. search_text("第1题" 或 题干关键词)      → 定位 para_id
4. get_paragraph(para_id)                 → 核对公式/选项原文
5. replace_text / modify_cell …            → tracked 修订
6. add_comment(para_id, "改题说明…")      → 可选
7. audit_document()
8. save_document(…-paper-q1-revised.docx)  → 新文件
9. generate_change_summary()              → 可选：给同事看的变更清单
```

### 含 WPS 公式 OLE（A/B 变式卷、选项里仍是旧卷公式）

MCP `replace_text` **改不到** OLE 内公式。已验证路径：**行内 OMML**（见 `skills/docx-mcp/lib/`）。

```
1. 复制母版 A → …-B-paper-inline-omml-pilot.docx（勿覆盖 A）
2. 编写 patches.json（或 Python patch 函数）：
   - text_replace：页眉「试卷类型 A→B」等
   - paragraphs[].index：Word 段落序号（1-based）
   - segments：交替 text / latex
3. python skills/docx-mcp/lib/rewrite_inline_omml.py --src A.docx --dst B-pilot.docx --patches patches.json
4. open_document(B-pilot) → audit_document() → save_document(定稿路径)
5. 用户在 Word/WPS 目视公式与行距 → 通过后扩到全卷 + answer.docx
```

示例补丁：`skills/docx-mcp/references/inline-omml-patches.example.json`（MATH1027 2025-2026-2 B 卷 pilot：选择 Q1 + 计算 Q4）。

Feature 换题真源仍放 `features/develop/<feature-id>/tech_design.md`；JSON/Python 只负责写入 docx。

**版式敏感区（慎改）：** 页眉、装订线、分值表、页边距 — 行内 OMML 流程只重建 **题目段落** 的 `w:r`；页眉小范围替换可用 `text_replace` 或 JSON `text_replace`。

## 与 pdf-exam-pipeline

| 需求 | 工具链 |
|---|---|
| Word 内改一题、保留学院卷面版式 | **docx-mcp**（本 Skill） |
| 已有 MinerU Markdown → YAML → XeLaTeX 重排 PDF | `skills/pdf-exam-pipeline/` |

MinerU / LaTeX 路径的样张与脚本见 `features/research/pdf-math-exam-to-latex-skill-survey/`；**日常定稿仍以 `repos/teaches/…/*.docx` 为主**。

## 共享模板

空白卷面模板（若有）：`repos/teaches/shared/templates/`。新建试卷时复制模板再按命名规范另存到对应 `exams/{AY}-{TERM}/`。

## 临时文件

解压 OOXML、试验性导出：**仅**放 `repos/teaches/tmp/`（已在 `.gitignore`），勿把中间产物提交进 `exams/`。
