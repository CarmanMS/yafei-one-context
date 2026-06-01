---
name: docx-mcp
description: 用 docx-mcp MCP 创建或修订 Word（.docx）；Markdown 转 docx、修订模式改稿、批注、试卷/合同审阅；需 Cursor 已启用 user-docx-mcp
triggers:
  - 改 Word
  - 改 docx
  - Word 文档
  - markdown 转 word
  - md 转 docx
  - 修订模式
  - 批注
  - 改试卷
  - 期末卷
  - 出卷
  - 合同审阅
  - docx-mcp
---

# docx-mcp — Word 文档（MCP）

通过 **MCP 服务器 `user-docx-mcp`** 读写 `.docx`：修订痕迹、批注、脚注、表格与结构校验。  
**MCP 只提供工具**；本 Skill 规定何时用、调用顺序与交付前检查。

## 何时启用

1. **显式触发**：用户提到 `triggers` 中任一词，或明确要用 Word MCP / docx-mcp。
2. **同线程延续**：已在本对话中打开或编辑某 `.docx` 时，后续对该文件的修改 **默认继续本 Skill**，除非用户改做 PDF/LaTeX 等非 docx 流程。

**不要用本 Skill：** PDF、Excel、legacy `.doc`（先转 `.docx`）。

## 强制执行顺序

1. **读 MCP 工具 schema（代理义务）**  
   首次调用前，用 `CallMcpTool` 前必须 Read：  
   `mcps/user-docx-mcp/tools/<tool>.json`（至少 `open_document`、`save_document`、`audit_document`）。  
   路径以 Cursor 工作区下的 MCP 描述符为准（本机常见：`C:\Users\<user>\.cursor\projects\<project>\mcps\user-docx-mcp\tools\`）。

2. **读工作流参考（按需）**  
   - 通用流程与工具表：`skills/docx-mcp/references/mcp-workflows.md`  
   - 教学试卷路径与改题约定：`skills/docx-mcp/references/teaches-exams.md`（涉及 `repos/teaches/` 时 **必读**）  
   - **含 WPS/Word 公式、需同行行内公式**：`skills/docx-mcp/lib/inline_omml.py` + `references/inline-omml-patches.example.json`（见下「行内 OMML」）

3. **执行 → 校验 → 保存**（见下「标准流程」）

4. **交付前门控**：`audit_document()` 通过后再 `save_document()`；涉及 footnote/结构改动时再跑 `validate_footnotes()` / `validate_paraids()`。

## MCP 调用约定

| 项 | 约定 |
|---|---|
| 服务器名 | `user-docx-mcp` |
| 调用方式 | `CallMcpTool`（先读 tool JSON schema） |
| 默认修订 | 编辑类工具默认 `tracked=True`（Word 中可见修订）；静默改写显式传 `tracked=False` |
| 并行多文档 | 每次 `open_document` / `create_from_markdown` 返回 `document_handle`；后续 **同一文档** 的所有工具调用带同一 handle；勿混用默认 `__default__` |
| 保存策略 | 改稿默认 **另存为新文件**，保留原稿；仅当用户明确要求覆盖时才 `save_document` 到原路径 |
| 改前核对 | `search_text` → `get_paragraph(para_id)` 确认原文，再 `replace_text` / `delete_text` + `insert_text` |

## 标准流程

### A. 修订已有文档

```
open_document(path) → get_headings() / get_document_info()
→ search_text(query) → get_paragraph(para_id)
→ replace_text / insert_text / delete_text / modify_cell …
→ audit_document()
→ save_document(output_path)   # 新路径
→ generate_change_summary()    # 可选：交付变更清单 .txt
```

### B. Markdown → docx

```
create_from_markdown(output_path, markdown=… 或 md_path=…)
→ audit_document()
→ save_document()
```

### C. 两份 docx 对比

```
diff_to_text(base_path, revised_path, …)   # 或 compare_documents
```

### D. 数学卷 / 含公式 OLE — 行内 OMML（MCP 改不动公式时）

**适用**：母版 `.docx` 里公式是 **WPS OLE** 或 `replace_text` 只改了中文、选项公式仍是旧卷；需要 **题干/选项同行** 公式（不是段后独立公式块）。

**做法**（已验证 Word/WPS 可打开）：

1. 从 **干净母版复制** 到新文件名（勿在旧草稿上叠改）。
2. 用 `skills/docx-mcp/lib/inline_omml.py` 或 CLI `lib/rewrite_inline_omml.py`。
   - 段落定位：段落序号（1-based）容易受表格、隐藏段落或嵌套容器等影响而变化。**强烈推荐使用 stable 唯一的 `w14:paraId` 定位段落**，先使用 `dump_paragraphs.py` 导出文档内所有段落的 `paraId` 和纯文本快照，再在补丁中填入 `para_id` 字段进行精确匹配。
   - 每段：`[{"kind": "text", "content": "…"}, {"kind": "latex", "content": r"…"}, …]` → 写入 `w:r` + 行内 `m:oMath`。
   - LaTeX→OMML：不要使用 docx-mcp 内部默认转换器（其对复杂极限、分数、多层根式和积分上下限的 MathML 扁平化转换有缺陷，容易造成积分限变为普通文本、分数丢失或换行错乱）。**本 Skill 已集成专用的 `mathml_to_omml_nodes` 深度递归映射与 OMath 语义翻译器**（在 `inline_omml.py` 中实现），可以完美保持以下高级排版：
     * **积分上下限 (msubsup)**：若 base_text 中含有 `∫`, `∬`, `∑` 等算子，自动转换为 `m:nary`（n-ary 积分结构）并设置 `m:limLoc` 为 `subSup`，确保积分的上下限上下对齐，保持标准学术排版。
     * **常规上下标 (msup/msub/sSubSup)**：转换非积分算子的上下标结构为 `m:sSup` / `m:sSub` / `m:sSubSup` 块，保持原汁原味的排版风格。
     * **传统公式外观一致性（老格式 - Times New Roman & 非斜体数字/符号）**：
       为使新写入的行内 OMML 与未改动的 A 卷旧 OLE 公式（WPS 3.0 编辑器等）在视觉上完美统一，系统自动采取以下优化（在 `lib/inline_omml.py` 内置实现）：
       a) **全局数学字体替换**：在 `rewrite_docx` 时，自动读取 `.docx` 的 `word/settings.xml`，将其中的默认数学字体由 Cambria Math 统一替换为 **Times New Roman**。
       b) **非斜体约束（数字、括号、标点、运算符）**：在转换 XML 时，对 `mo`/`mn`/`mtext` 节点（包括所有的括号、数字、逗号等非字母符号），自动在 OMML 节点内追加 `<m:rPr><m:sty m:val="p"/></m:rPr>` 属性，强制其渲染为标准正体（非斜体），仅保留单个变量字母为数学斜体，使其字体、字形及斜体规范与老公式编辑器完美兼容。
     * **分数 (mfrac)**：转换 MathML 的 `mfrac` 为 `m:f` / `m:num` / `m:den` 结构。
     * **根式 (msqrt/mroot)**：转换 MathML 的 `msqrt` 或 `mroot` 为 `m:rad` 的平方根或高阶根式结构。
     * **排版细节（去重与紧凑）**：题干和选项文本中，如果 A 卷使用了 WPS 自动列表（如自动题号 `1.` 或自动选项 `(A)`），在重构段落时，**切勿**在 segments 的第一个 text 节点中重复录入题号或选项，否则会出现 `1. 1.` 或 `(A) (A)` 的重复序号现象。选项之间使用适量空格或独立制表符排列，避免 option 换行。
3. `open_document` → `audit_document()` → 另存定稿。

```powershell
python skills/docx-mcp/lib/rewrite_inline_omml.py `
  --src path/to/A-paper.docx `
  --dst path/to/B-pilot.docx `
  --patches skills/docx-mcp/references/inline-omml-patches.example.json
```

补丁格式：`references/inline-omml-patches.example.json`（`paragraphs[].segments`，支持 `para_id` 精确寻址与 `kind: "text" | "latex"` 配置）。

**Python 嵌入**（整卷逻辑复杂时）：

```python
from pathlib import Path
import sys
sys.path.insert(0, "skills/docx-mcp/lib")
from inline_omml import patch_paragraph_by_para_id, replace_exam_paper_type, rewrite_docx

def patch(root):
    # 完美替换页眉/题头纸张类型 B (支持 w:t 被分割情况)
    replace_exam_paper_type(root, "B")
    # 使用唯一的 paraId 精确寻址并重构，保留题干与高级 OMML 排版
    patch_paragraph_by_para_id(root, "266234FE", [
        {"kind": "text", "content": "设 "},
        {"kind": "latex", "content": r"F(x)=\int_0^x (t+1)e^{-t}\,dt"},
        {"kind": "text", "content": "，则 "},
        {"kind": "latex", "content": r"F'(x)"},
        {"kind": "text", "content": "=(        )．"}
    ])
```,old_string:

rewrite_docx(Path("A-paper.docx"), Path("B-paper.docx"), patch)
```

依赖：`pip install latex2mathml lxml`（docx-mcp 已装则 OMML 转换器可用）。

## 与 pdf-exam-pipeline 的分工

| 场景 | 走哪里 |
|---|---|
| 直接在 Word 里改题、改表述、加批注、保留版式 | **本 Skill（docx-mcp）** |
| MinerU MD → YAML → LaTeX/PDF 整卷重排 | `skills/pdf-exam-pipeline/` |

`repos/teaches/` 下 **源稿以 `.docx` 为准**；见 `skills/docx-mcp/references/teaches-exams.md`。

## 反模式

- 未 `open_document` 就改内容  
- 未 `audit_document` 就保存  
- 猜测 `para_id` 或文本（必须先 `search_text` + `get_paragraph`）  
- 对整段做过大范围 tracked 替换（只标真正变化的部分）  
- 生产环境单独依赖 `scrub_pii`（实验性，见 `skills/docx-mcp/references/mcp-workflows.md`）  
- **含 WPS 公式 OLE 的数学卷** 仅用 `replace_text` / `add_equation`（改不到 OLE；段后公式版式不对）→ 用 **`lib/inline_omml.py`**

## Resources

| 文件 | 内容 |
|---|---|
| `skills/docx-mcp/references/mcp-workflows.md` | 工具速查、OOXML 要点、审计清单 |
| `skills/docx-mcp/references/teaches-exams.md` | `repos/teaches/` 命名、改题后缀、与 pdf-exam-pipeline 衔接 |
| `skills/docx-mcp/lib/inline_omml.py` | **行内 OMML** 写入（LaTeX 片段 + 段落重建） |
| `skills/docx-mcp/lib/rewrite_inline_omml.py` | JSON 补丁 CLI |
| `skills/docx-mcp/references/inline-omml-patches.example.json` | 补丁 JSON 示例（MATH1027 B 卷 pilot 三题） |
