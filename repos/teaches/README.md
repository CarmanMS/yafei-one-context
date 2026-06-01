# Teaching — 大学数学教学资产

本目录纳入 **one-context 主库**，存放课程、试卷等教学材料（非独立 Git 子仓）。

## 目录结构

```text
repos/teaches/
├── README.md                 # 本说明
├── courses/
│   └── {COURSE_CODE}/        # 一门课一个目录，如 MATH1027
│       ├── course.yaml       # 课号、中文名、学院等元数据
│       └── exams/
│           └── {AY}-{TERM}/  # 学年-学期，如 2025-2026-2
│               ├── {AY}-{TERM}-{CODE}-{type}-{paper}-paper.docx
│               ├── {AY}-{TERM}-{CODE}-{type}-{paper}-answer.docx
│               └── {AY}-{TERM}-{CODE}-{type}-{paper}-paper.pdf   # 可选导出
├── shared/
│   └── templates/            # 空白卷面模板（页眉、装订线、分值表）
└── tmp/                      # 不入库：docx 解压、Markdown 导出试验
```

## 文件命名规范

```text
{学年}-{学期}-{课号}-{考试类型}-{试卷号}-{角色}.{扩展名}
```

| 字段 | 示例 | 说明 |
|------|------|------|
| 学年 | `2025-2026` | 跨日历年 |
| 学期 | `2` | `1` 第一学期，`2` 第二学期 |
| 课号 | `MATH1027` | 学校课程编号 |
| 考试类型 | `final` | `final` 期末、`mid` 期中、`quiz` 小测 |
| 试卷号 | `A` / `B` | 同批次 A/B 卷 |
| 角色 | `paper` / `answer` | 试卷正文 / 参考答案 |

**示例**

- `2025-2026-2-MATH1027-final-A-paper.docx` — 2025–2026 第二学期高数 B（二）期末 A 卷
- `2025-2026-2-MATH1027-final-A-answer.docx` — 同上，答案
- `2025-2026-2-MATH1027-final-A-paper.pdf` — 定稿 PDF 导出

改题草稿可在同目录追加后缀，如 `…-paper-q1-revised.docx`。

## 新建一门课

1. 创建 `courses/{COURSE_CODE}/course.yaml`
2. 创建 `courses/{COURSE_CODE}/exams/{AY}-{TERM}/`
3. 从 `shared/templates/` 复制空白模板（若有）再另存为规范文件名

## 与 skills 的关系

| 场景 | Skill |
|------|--------|
| 在 Word 里改题、批注、保留卷面版式 | `skills/docx-mcp/`（MCP `user-docx-mcp`） |
| MinerU MD → YAML → LaTeX/PDF 整卷重排 | `skills/pdf-exam-pipeline/` |

**源稿以本目录 `.docx` 为准**；docx 路径与改题命名见 `skills/docx-mcp/references/teaches-exams.md`。
