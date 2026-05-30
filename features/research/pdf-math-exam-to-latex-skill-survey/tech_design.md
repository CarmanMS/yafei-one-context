# 技术方案 — 参考卷版式 · AI 可编辑 · 可再出 PDF

**关联**：`spec.md`、`survey-report.md`  
**状态**：MVP 设计（2026-05-25）  
**用户确认**：① 不用 Word；② 本机可装工具；③ MVP 先走 **AI 自动改题** 再导出 PDF。

---

## 1. 目标闭环

```text
参考卷 PDF
    → 结构化解析（MinerU + 规则/LLM）
    → 可编辑源稿（YAML 题库 + LaTeX 模板，AI 改字段）
    → AI 改题 / 出新题（同版式、同题型结构）
    → xelatex 编译
    → 新试卷 PDF（版式贴近参考卷）
```

**验收（MVP）**：

- 从样张 **CASE-A 第 1 页** 得到 `questions.page1.yaml`（≥1 道选择题，公式为 LaTeX 字符串）。
- **AI 自动修改**：替换数值/改题干表述，或生成 1 道同结构新题。
- `build.ps1` / `build.py` 生成 `output/paper.pdf`，版式含：学校抬头区、题型标题、题号、A/B/C/D、分值。
- 源稿全程 **文本可 diff**，禁止「只能改 PDF 像素」。

---

## 2. 为什么不用 Word

| 格式 | AI 可编辑 | 数学公式 | 版式可控 | PDF 往返 |
|------|-----------|----------|----------|----------|
| Word | 中（OMML 易坏） | 差 | 中 | 有 |
| Markdown 裸稿 | 好 | 中（`$$`） | **差**（试卷版式） | 需再排版 |
| **YAML + LaTeX 模板** | **很好** | **好** | **好** | **好** |
| 纯 LaTeX 单文件 | 好 | 很好 | 好 | 好 |

**选定**：**YAML 题目结构**（AI 主改） + **`templates/exam-zh.tex`**（版式真源，人偶尔改） + **Jinja2 渲染** → `build/paper.tex` → PDF。

AI 只改 YAML 里的 `stem`、`choices`、`points`、`figures`，避免整份 `.tex` 被模型写坏括号/环境。

---

## 3. 费用说明（本机方案）

| 组件 | 是否收费 | 说明 |
|------|----------|------|
| **MinerU** | **免费开源**（AGPL-3.0） | 本机安装；首次会 **下载模型**（数 GB，无订阅费）；CPU 可跑，GPU 更快 |
| **TeX Live / MiKTeX** | **免费** | `xelatex` 出 PDF；首次安装体积大 |
| **Python 依赖** | 免费 | `mineru[core]`、`jinja2`、`pyyaml` 等 |
| **Cursor / LLM 改题** | **按你的 API 套餐** | MVP 用当前对话即可；非 MinerU 费用 |
| **Mathpix / 云端 Vision** | 可选、按量 | MVP **不依赖**；MinerU 不够再考虑 |

**结论**：本机试点 **不需要向 MinerU 官方付费**；主要成本是 **磁盘 + 时间 +（可选）LLM token**。

---

## 4. 架构

```text
features/research/pdf-math-exam-to-latex-skill-survey/
  pilot/
    README.md              # 安装与跑通步骤
    ingest_mineru.ps1      # PDF → MinerU → md/
    parse_md_to_yaml.py    # md → questions/*.yaml（规则 + 可选 LLM）
    ai_revise_questions.py # 调用 LLM 改题（或 Agent 手改 yaml）
    build_paper.py         # yaml + template → tex → pdf
    templates/
      exam-zh.tex.j2       # 版式模板（对齐树人学院期末卷）
    schemas/
      questions.schema.yaml
    output/                # gitignore：tex/pdf/md
  samples/                 # 仅说明，不放 PDF
```

**后续入库**：验证通过后，整体迁入 `skills/pdf-exam-pipeline/` 或挂到 `math-teacher-ai-platform`。

---

## 5. 数据模型（AI 可编辑）

```yaml
# questions/paper-2024-a-p1.yaml
meta:
  title: "高等数学B类 期末考试试卷（A）"
  course_id: "MATH1027"
  academic_year: "2023-2024-2"
  total_points: 100

sections:
  - id: sec-1
    title: "一、选择题"
    instruction: "本题共5小题，每小题3分，共15分。"
    questions:
      - id: q1
        points: 3
        stem: |
          设 $f(x)$ 在 $x=0$ 处可导，则 …
        choices:
          A: "$0$"
          B: "$1$"
          C: "$2$"
          D: "$3$"
        answer: "B"          # 可选，出题时可清空
        figure: null         # 或 "figures/q1.png"
```

**AI 改题指令示例**（MVP）：

- 「把 q1 改为考查导数定义，数值换成 …，保持四选项单选」
- 「复制 q1 结构新增 q1b，难度略升」

模型 **只输出 YAML diff** 或完整 YAML，由脚本校验 schema 后渲染。

---

## 6. 解析链路（PDF → YAML）

| 步骤 | 工具 | 输出 |
|------|------|------|
| 1 | MinerU `mineru -p file.pdf -o out -f true -s 0 -e 0` | `out/*/auto/*.md` + 图片 |
| 2 | `parse_md_to_yaml.py` | 按「一、」「(1)」「A.」等正则 + LLM 纠错 → YAML |
| 3 | 人工/AI 校对 | 修正碎公式、题号错位 |

**已知风险**（见调研报告）：MinerU 对 **习题/试卷版式** 官方自述偏弱 → MVP 以 **第 1 页** 验公式+题干预案，不行则加 **pix2tex** 补公式图块。

---

## 7. 渲染链路（YAML → PDF）

| 步骤 | 命令 |
|------|------|
| 1 | `python build_paper.py --input questions/...yaml --template templates/exam-zh.tex.j2` |
| 2 | 生成 `output/paper.tex` |
| 3 | `xelatex -interaction=nonstopmode paper.tex`（两次，处理目录/页码） |

**模板能力**（对齐参考 PDF）：

- `ctexart` + 中文
- 页眉：课程号、学年、卷别
- `\section*{一、选择题}` + 说明行
- `\begin{enumerate}` + `\begin{enumerate}[label=\Alph*.]` 选项
- 插图 `\includegraphics[width=...]{...}`

---

## 8. AI 改题（MVP 默认开启）

**流程**：

1. 读取 `questions/*.yaml` + `schemas/questions.schema.yaml`
2. LLM 任务：`revise`（改数值/考点）或 `generate_one`（同结构新题）
3. 写回 `questions/*.revised.yaml`
4. `build_paper.py` → PDF

**约束 prompt**：

- 公式必须用 `$...$` 或 `$$...$$`（LaTeX）
- 不得删 `sections` 结构；题量可先保持 1 题试点
- 输出仅 YAML，无 markdown 包裹

---

## 9. MVP 范围与不做

| MVP 做 | MVP 不做 |
|--------|----------|
| CASE-A **第 1 页** 解析 + 1 题 YAML | 全 6 页自动完美还原 |
| AI 改 1 题 + 出 PDF | 与 FunctionCanvas 前端集成 |
| 本机 MinerU + xelatex | Word 导出 |
| 费用说明与安装文档 | 商业 Mathpix 依赖 |

---

## 10. 验证计划

| 编号 | 检查项 | 通过标准 |
|------|--------|----------|
| V1 | MinerU 安装 | `mineru --help` 成功 |
| V2 | 第 1 页 MD | 存在 `$$...$$` 公式块 |
| V3 | YAML | schema 校验通过，含 stem + 4 choices |
| V4 | AI 改题 | revised yaml 与原版 diff 可读 |
| V5 | PDF | `output/paper.pdf` 生成，无 xelatex 致命错误 |
| V6 | 版式 | 目视：有题型标题、题号、选项行 |

结果记入 `test_report.md`（试点完成后创建）。

---

## 11. 与 math-teacher-ai-platform

- Phase 1 出题 MVP 的 **导出 PDF** 可复用本方案的 **YAML + 模板渲染**。
- 可视化题图：继续用 Math Canvas 导出 PNG → YAML `figure` 字段。
- 本产品 feature 验证通过后再 **抽 skill**，避免研究目录堆实现代码过久。

---

## 12. 开放项（实现时处理）

- MinerU 输出目录结构随版本变化 → `ingest_mineru.ps1` 做路径探测
- 选择题「题干+选项」粘连 → `parse_md_to_yaml` 用 LLM 二次切分
- 装订线/答题栏 → 模板二期用 `eso-pic` 或固定 `\vspace` 微调
