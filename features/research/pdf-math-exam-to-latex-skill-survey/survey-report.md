# 调研报告：数学试卷 PDF → LaTeX

**日期**：2026-05-25  
**状态**：初版完成（样张为 **结构诊断 + 文献/仓库调研**；本机未批量跑通 MinerU/Marker 全链路）  
**调研假设**（开放问题未回复时的默认）：不绑定 exam 模板；接受 80% 自动 + 人工校对；云端方案可列但不默认；样张以用户 Downloads 两份期末卷为准。

---

## 1. 结论摘要

| 结论 | 说明 |
|------|------|
| **真·一键 PDF→可编译 `.tex` 的成熟 Skill 极少** | 多数为 **PDF→Markdown（内嵌 `$$…$$` LaTeX）** 或 **整页 Vision 重建 LaTeX** |
| **你的两份样张属「电子版试卷、有文字层」** | PyMuPDF 可抽出中文题干与题号，但 **公式在文本层被拆碎**（`sin`/分数/积分号多行断开），**不能**靠 `pdftotext` 直接得到可靠 `.tex` |
| **试卷版式（装订线、答题栏、选择题排版）** | 通用工具普遍弱；MinerU 文档明确写 **习题/试卷类解析效果不佳** |
| **建议路线** | **试点 B**：MinerU（或 Marker）→ `*.md`（公式 LaTeX 块）→ 模板化转 `exam`/`ctexart`；**试点 A**：`latex-document-skill`（Vision 按页 OCR 写 `.tex`，需多模态 API） |
| **one-context** | **建议观望新建 `skills/pdf-to-latex`**；优先 **包装「PDF→MD+公式 LaTeX→后处理 .tex」** 或引用上游 Skill，避免重复造轮子 |

---

## 2. 样张 Case Study（用户 Downloads）

**勿将完整 PDF 提交 Git**；路径仅本机留存。

| 样张 | 页数 | 类型 | 诊断 |
|------|------|------|------|
| `2023-2024-2高等数学B类上学期期末试卷A.pdf` | 6 | A 电子版 | 首页无嵌入图；文本层含中文+英文（MATH1027）；公式片段可搜到 `sin`/`ln`/`dx` 等但 **非完整 LaTeX** |
| `2022-2023-2高等数学B类上学期期末试卷A.pdf` | 6 | A 电子版 | 首页 **1 张嵌入图**（示意图类）；题干中文可提取；公式同样 **行级碎裂** |

**共同特征（高数期末卷）**：

- 学校抬头、课程编号、题型说明（一、选择题…）
- 选择题 A/B/C/D、分值、题号
- 大量 **行间公式 + 分数/根号/积分号**；部分题含 **几何示意图**
- 非扫描件，但 **不等于** 公式已是 LaTeX——PDF 内多为排版 glyph，抽取后需 **公式识别或 VLM**

**对工具的含义**：

- **仅文本管道**（MarkItDown、朴素 `get_text`）→ 题干可用，公式 **不可用**
- **公式管道**（MinerU `-f`、Marker、Mathpix）→ 必要
- **整页 Vision→TeX**（latex-document-skill）→ 版式最接近「整卷 .tex」，成本最高

---

## 3. 真·LaTeX vs 中间态（分类说明）

| 类别 | 含义 | 代表 |
|------|------|------|
| **① 直接 `.tex`** | 目标为可编译 TeX 源文件 | latex-document-skill（Vision 按页生成） |
| **② MD/JSON + 内嵌 LaTeX** | 主输出 Markdown，公式为 `$$…$$` | MinerU、Marker、Nougat |
| **③ 仅公式 LaTeX** | 裁切公式图 → 单行 TeX | pix2tex / LaTeX-OCR |
| **④ 非 LaTeX** | 纯文本/HTML/Word | MarkItDown、pdf2docx |

本报告 **TOP 推荐** 以 ①② 为主；③ 作补充组件。

---

## 4. 候选方案对比表（18 条）

| # | 名称 | 类型 | 来源 | 输出形态 | 公式保真 | 版式/试卷 | 中文 | Agent Skill | 样张相关性 | 推荐级 |
|---|------|------|------|----------|----------|-----------|------|-------------|------------|--------|
| 1 | **latex-document-skill** | Skill+脚本 | [ndpvt-web/latex-document-skill](https://github.com/ndpvt-web/latex-document-skill) | **① `.tex`** | 高（Vision 按页） | 中（需 profile 调） | 中（靠 OCR） | **有 SKILL.md** | 与样张最贴：整页含公式 | **可直接用*** |
| 2 | **MinerU** | CLI/API | [opendatalab/MinerU](https://github.com/opendatalab/MinerU) | **② MD+JSON** | 高（公式→LaTeX） | 低（**自述习题/试卷差**） | 高 | 无官方 Skill | 样张属其弱项场景 | **需二次开发** |
| 3 | **Marker** | CLI | [datalab-to/marker](https://github.com/datalab-to/marker) | **② MD** | 高 | 中 | 中 | 社区 Skill 可包一层 | 未本机跑；同类试卷风险 | **需二次开发** |
| 4 | **LaTeX-OCR (pix2tex)** | CLI/GUI | [lukas-blecher/LaTeX-OCR](https://github.com/lukas-blecher/LaTeX-OCR) | **③ 公式片段** | 很高（单公式） | 不适用 | 不适用 | 无 | 裁切公式区后补全 | **组件** |
| 5 | **Mathpix Snip/API** | 商业 API | [mathpix.com](https://mathpix.com/) | ③ + 部分 MD | 很高 | 低 | 中 | 无 | 公式准、按量付费 | **需二次开发** |
| 6 | **Nougat** | 模型/CLI | [facebookresearch/nougat](https://github.com/facebookresearch/nougat) | **② MD（类 LaTeX）** | 高（论文） | 低 | 弱（偏英文学术） | 无 | 试卷非目标域 | 仅作参考 |
| 7 | **InftyReader** | 商业桌面 | [inftyreader.com](https://www.inftyreader.com/) | ①/专有格式 | 高（学术） | 中 | 中 | 无 | 日文/数学文献向 | 仅作参考 |
| 8 | **Mathpix Markdown PDF** | 商业 | Mathpix PDF→MD | ② | 高 | 中 | 中 | 无 | 与 MinerU 类似 | 需二次开发 |
| 9 | **Microsoft MarkItDown** | CLI/库 | [microsoft/markitdown](https://github.com/microsoft/markitdown) | ④ 文本 MD | **低**（公式常丢） | 低 | 中 | 本仓 playbook | 样张公式不可靠 | 不推荐 |
| 10 | **pdf-to-markdown**（用户侧） | Skill | 个人/Claude 生态 | ④ MD | 低 | 低 | 中 | 有 | 同 MarkItDown 类 | 不推荐 |
| 11 | **book-to-skill-distillation** | Skill | [huangzesen/book-to-skill-distillation](https://github.com/huangzesen/book-to-skill-distillation) | 知识蒸馏非 TeX | — | — | 中 | **有** | 扫描 PDF OCR→文本，**非 LaTeX** | 不推荐 |
| 12 | **math-images-skill** | Skill | [juntao/math-images-skill](https://github.com/juntao/math-images-skill) | **LaTeX→PNG** | — | — | — | **有** | 方向相反 | 不推荐 |
| 13 | **Pandoc** | CLI | [pandoc.org](https://pandoc.org/) | MD/DOCX→TeX | 取决于上游 | 中 | 高 | 无 | **不能**直接读 PDF | 后处理用 |
| 14 | **pdf2latex（各类老旧）** | CLI | 零散项目 | ① 部分 | 低 | 低 | 低 | 无 | 维护差 | 不推荐 |
| 15 | **Docling (IBM)** | 库/CLI | [DS4SD/docling](https://github.com/DS4SD/docling) | ② MD/JSON | 中高 | 中 | 中 | 无 | 通用文档；试卷未验证 | 仅作参考 |
| 16 | **GPT/Claude + 页图** | 工作流 | 各厂商 API | ① 或 ② | 高 | 中 | 高 | 可自写 Skill | 与 latex-document-skill 同类 | **可直接用*** |
| 17 | **surya / paddle OCR + 自拼** | 自研 | 开源 OCR | ④ 文本 | 低 | 低 | 高 | 自研 | 工作量大 | 不推荐 |
| 18 | **OmniDocBench 类 VLM 工具链** | 研究/产品 | 多家 2025 论文配套 | ② 为主 | 高 | 待验证 | 中 | 少见 | 趋势：MD+LaTeX 块 | 观望 |

\* **可直接用** = 需 **多模态 API 费用** + 人工校对，不是零成本全自动。

---

## 5. TOP 3 推荐

### 1）latex-document-skill（Vision 整页 → `.tex`）

- **理由**：少数明确面向「**把 PDF/扫描页变成可编译 LaTeX**」的 **Agent Skill**；含 `pdf_to_images.sh`、`math-notes.md` profile、批量页并行策略。
- **风险**：依赖 **Vision 模型 API**；6 页期末卷成本可控，但版式需人工改 `exam` 类模板；中文试卷需实测 profile。
- **与样张**：你的 PDF 可先 **200 DPI 出图** 再 OCR，绕过碎裂的文本层公式。

### 2）MinerU（PDF → Markdown，公式为 LaTeX）

- **理由**：开源活跃（2025 MinerU2.5）、**公式默认识别为 LaTeX**、支持本地 GPU/CPU；适合进 Agent 流水线（MD→再转 TeX）。
- **风险**：官方限制写明 **「小学课本、习题」解析不好**——与你的 **期末试卷** 高度重叠；输出 **不是** 整份 `.tex`，需写 **MD→exam.tex** 转换器。
- **与样张**：建议你对 **仅第 1 页** 跑 `mineru -p … -o … -f true` 做 Go/No-Go，再决定是否全卷。

### 3）LaTeX-OCR + 页图渲染（公式组件）

- **理由**：对 **裁切后的公式区域** 质量稳定、可离线、MIT；与 1）或 2）组合：正文/题号走 MinerU，疑难公式图走 pix2tex。
- **风险**：不负责题号、选项、分页；纯体力裁切或需版面检测。

---

## 6. 是否存在「现成 PDF→LaTeX」Skill？

| 仓库 | 有 SKILL.md？ | 直接输出 .tex？ |
|------|---------------|-----------------|
| latex-document-skill | 是 | **是**（Vision 管线） |
| math-images-skill | 是 | 否（反向） |
| book-to-skill-distillation | 是 | 否 |
| MinerU / Marker / pix2tex | 否（CLI 为主） | 否 / 片段 |

**Anthropic 官方 skills 列表** 中 **未发现** 专用 `pdf-to-latex`；社区以 **文档解析→MD** 为主。

---

## 7. 建议试点（基于你的 2 份 PDF）

| 试点 | 步骤 | 验收（第 1 页即可） |
|------|------|---------------------|
| **P0 诊断** | PyMuPDF 抽文本（已完成） | 题干中文可读；公式不可直接用 |
| **P1 MinerU** | `mineru -p <2024试卷> -o tmp/mineru -s 0 -e 0 -f true` | 得 `*.md`，含 `$$…$$`；核对第 1 题公式 |
| **P2 Marker** | 同页对比（可选） | 与 P1 比公式错误率 |
| **P3 Vision** | latex-document-skill 或 Cursor 读 **页图** 生成 `page1.tex` | 能否 `xelatex` 通过 |
| **P4 组装** | Pandoc/脚本：MD → `ctexart`+`exam` 骨架 | 题号、选项环境是否可接受 |

样张 **不入库**；试点产物放 `features/.../tmp/` 或本机 Downloads 旁。

---

## 8. 与 math-teacher-ai-platform 衔接

- **入库路径**：试卷 PDF → 结构化 MD（MinerU）或 `.tex`（Vision）→ 题库 JSON（题号、题干、选项、公式 LaTeX、配图路径）→ 现有出题/组卷 UI。
- **不必** 强求一次生成完美印刷版 TeX；可先 **「LaTeX 公式字段 + Markdown 题干」** 双存。
- 若产品要 **教师可编辑**，优先 **MD+公式** 编辑体验；若要高保真排版再导出 TeX/PDF。

---

## 9. one-context 建议

| 项 | 建议 |
|----|------|
| 新建 `skills/pdf-to-latex` | **观望** → 更现实是 **`skills/pdf-exam-to-markdown`**（封装 MinerU/Marker）+ **`knowledge/playbooks/pdf-exam-latex-pipeline.md`** |
| 复用 | `use-microsoft-markitdown` 仅作纯文字 PDF；**数学卷不要用** |
| 依赖 | Windows 上 MinerU 需 Python/GPU 环境；Vision 路线需 API 预算 |

---

## 10. 仍需你决策的 4 项

| # | 问题 | 影响 | 建议选项 |
|---|------|------|----------|
| 1 | 最终要 **`.tex` 可印刷`** 还是 **「公式 LaTeX + 题干 MD」即可**？ | 决定是否必须 Vision/整页重建 | A 必须 TeX / B MD 即可 |
| 2 | 能否用 **云端**（OpenAI/Claude/Mathpix）？ | 过滤 latex-document-skill、Mathpix | 能 / 必须离线 |
| 3 | 是否愿意在本机 **试装 MinerU**（约 2–8GB 级模型下载）？ | 决定 P1 实测 | 愿意 / 仅云 API |
| 4 | 样张是否可提供 **脱敏 1 页** 给仓库 `samples/`（截图 PNG，非 PDF）？ | 便于 CI/文档复现 | 可以 / 仅本机 |

---

## 11. spec 验收自检

- [x] ≥15 条候选且有链接  
- [x] 公式/输出/Agent/样张列齐全  
- [x] 区分真·LaTeX vs MD 中间态  
- [x] TOP 3 + 风险  
- [x] Skill 的 SKILL.md 情况  
- [x] math-teacher-ai-platform 衔接  
- [x] 是否新建 one-context skill  

---

**报告路径**：`features/research/pdf-math-exam-to-latex-skill-survey/survey-report.md`
