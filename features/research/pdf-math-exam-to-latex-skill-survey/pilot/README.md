# MVP 试点 — 安装与验证

**目标**：参考卷 PDF 第 1 页 → YAML → **AI 改题** → PDF。

**费用**：MinerU、TeX、Python 库均 **免费**；仅 LLM 改题消耗你的 API 额度（在 Cursor 里做可不计额外 MinerU 费用）。

---

## 0. 前置

- 样张路径（本机）：`%USERPROFILE%\Downloads\2023-2024-2高等数学B类上学期期末试卷A.pdf`
- 勿将 PDF 提交 Git

---

## 1. 安装（Windows，PowerShell）

### 1.1 Python 3.10+

```powershell
python --version
```

### 1.2 MinerU（免费，首次下载模型较慢）

```powershell
cd D:\harnessworld\one-context
python -m venv .venv-pdf-exam
.\.venv-pdf-exam\Scripts\Activate.ps1
pip install -U "mineru[core]" jinja2 pyyaml jsonschema
```

验证：

```powershell
mineru --help
```

> 若 `mineru` 不在 PATH，用：`python -m mineru.cli.main --help`（以实际包为准）。

### 1.3 TeX（xelatex，免费）

安装 **MiKTeX** 或 **TeX Live**，保证命令行可用：

```powershell
xelatex --version
```

首次编译会自动装缺失宏包（`geometry`、`enumitem` 等，约 10–30 秒）。模板使用 **fontspec + Microsoft YaHei**（非 `ctexart`，避免首次卡住）。

---

## 2. 跑通（第 1 页）

在仓库根、已激活 venv 时：

```powershell
cd features\research\pdf-math-exam-to-latex-skill-survey\pilot

# 1) PDF → Markdown（仅第 1 页可后处理截断）
.\ingest_mineru.ps1 -PdfPath "$env:USERPROFILE\Downloads\2023-2024-2高等数学B类上学期期末试卷A.pdf"

# 2) MD → YAML（MVP 可先手改 yaml，再跑构建）
python parse_md_to_yaml.py --md output\mineru\**\*.md --out questions\page1.yaml

# 3) AI 改题（或在 Cursor 中编辑 questions\page1.yaml 后另存 revised）
python ai_revise_questions.py --in questions\page1.yaml --out questions\page1.revised.yaml

# 4) YAML → PDF
python build_paper.py --input questions\page1.revised.yaml --out output\paper.pdf
```

---

## 3. 验收

见 `../tech_design.md` 第 10 节 V1–V6。**2026-05-26 stub 试点已通过**，见 `../test_report.md`。

---

## 4. 故障排除

| 现象 | 处理 |
|------|------|
| MinerU 很慢 | 正常；CPU 模式；可加 `-d cuda`（有 NVIDIA GPU 时） |
| 公式仍是乱码 | 对单题截图跑 pix2tex，手动写入 yaml |
| xelatex 很久无 PDF | 先 `mpm --install=geometry`；勿用 `ctexart`；杀僵死进程：`Get-Process xelatex \| Stop-Process` |
| xelatex 缺字体 | 模板已用 `Microsoft YaHei`；或 MiKTeX 安装 `fontspec` |
| 试卷版式乱 | 改 `templates/exam-zh.tex.j2`，不是改 MinerU 输出 |
