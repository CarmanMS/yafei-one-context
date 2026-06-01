# docx-mcp — 工作流与工具速查

> MCP 服务器：`user-docx-mcp`。完整 upstream 说明见本机 `~/.claude/skills/docx-mcp/SKILL.md`（若存在）；本文件为 one-context 内精简版。

## 生命周期

| 工具 | 用途 |
|---|---|
| `open_document` | 打开 `.docx` |
| `create_document` | 空白或从 `.dotx` 模板 |
| `create_from_markdown` | Markdown → docx（标题、列表、表格、脚注、代码块等） |
| `save_document` | 保存（可另存） |
| `close_document` | 释放会话 |
| `get_document_info` | 段落数、脚注等概览 |

## 读取与定位

| 工具 | 用途 |
|---|---|
| `get_headings` | 标题树 + `para_id` |
| `search_text` | 正文/脚注/批注内查找（支持 `regex`） |
| `get_paragraph` | 按 `para_id` 取全文（改前必查） |

**para_id**：8 位十六进制（如 `1A2B3C4D`），来自 `get_headings` 或 `search_text`。

## 修订（默认 tracked=True）

| 工具 | 用途 |
|---|---|
| `replace_text` | 一步替换（优先于 delete+insert） |
| `insert_text` | 插入；`position`: `start` / `end` / 某子串之后 |
| `delete_text` | 删除 |
| `modify_cell` | 改表格单元格 |
| `edit_header_footer` | 页眉页脚 |
| `set_formatting` | 粗体/颜色等（带修订） |
| `add_comment` | 段落批注 |
| `get_tracked_changes` / `accept_changes` / `reject_changes` | 列示或处理修订 |

静默改写：上述编辑工具传 `tracked=False`。

## 表格 / 脚注 / 导出

| 工具 | 用途 |
|---|---|
| `get_tables` / `add_table` / `modify_cell` / `add_table_row` | 表格 |
| `add_footnote` / `validate_footnotes` | 脚注（勿重复 `add_footnote` 同一内容；后续引用用 `add_footnote_ref`） |
| `generate_change_summary` | 当前打开文档的变更 `.txt` |
| `diff_to_text` / `compare_documents` | 两文件 diff |
| `remove_watermark` | 去 DRAFT 水印 |
| `export_markdown` / `convert_to_pdf` | 导出（若 schema 中存在） |

## 交付前审计（必做）

```
audit_document()
```

必要时追加：

```
validate_footnotes()    # 动过脚注
validate_paraids()      # 动过结构/复制段落
```

`audit_document` 会检查：XML 良构、footnote 引用、paraId 唯一且 < 0x80000000、标题层级、书签、关系与图片引用、残留 DRAFT/TODO 等。

## 行内 OMML（含 WPS 公式 OLE 的数学卷）

| 情况 | 做法 |
|---|---|
| 纯文字 / 无嵌入公式 | MCP `replace_text` 等（上表） |
| 公式在 **WPS OLE** 里，`replace_text` 改不到 | **`skills/docx-mcp/lib/inline_omml.py`**：整段重建 + 行内 `m:oMath` |
| 需要段落后单独一行公式 | MCP `add_equation`（`m:oMathPara`，**非** 同行选项排版） |
| 需要同行题干/选项公式 | **`inline_omml.rebuild_paragraph`** 或 `rewrite_inline_omml.py --patches` |

要点：

- 用 **lxml** 写 `word/document.xml`，保留 `w:pPr`；`xml.etree.ElementTree.tostring` 易让 Word 报「文件损坏」
- 段落序号 **1-based**，与 Word `Paragraphs(i)` 一致
- 补丁 JSON：`references/inline-omml-patches.example.json`
- 改完后仍走 MCP：`open_document` → `audit_document` → `save_document`

## OOXML 要点（防 silent 损坏）

| 风险 | 规则 |
|---|---|
| paraId 重复或 ≥ 0x80000000 | 跑 `validate_paraids()` |
| 脚注 id 一对多引用 | 跑 `validate_footnotes()`；真实脚注从 id=1 起 |
| 空格匹配失败 | Word 常用 `\xa0`；用 `search_text`，勿裸字符串猜 |
| 标题编号 | **不要**在标题文字里写死「1.1」；用 Word 多级列表 |
| 整段删除 | 需同时处理段落标记的 `<w:del/>`，否则接受修订后留空段 |

## scrub_pii（实验性）

`scrub_pii` **不得**作为唯一脱敏手段；先 `dry_run=True` 人工核对。邮箱/电话等规则检测较可靠；人名 NER 易漏。
