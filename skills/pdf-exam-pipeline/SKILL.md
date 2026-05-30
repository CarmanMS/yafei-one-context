# pdf-exam-pipeline

数学期末卷 PDF → MinerU MD → YAML →（单题替换）→ 原卷版式 PDF。

## 适用场景

- 已有 MinerU 导出的 `*.md`，需要结构化题目并改一题后按**原卷版式**再出 PDF
- 样张：`features/research/pdf-math-exam-to-latex-skill-survey/pilot/output/mineru/`

## 依赖

- Python 3.10+：`pyyaml`, `jinja2`
- 本机 `xelatex`（MiKTeX / TeX Live）+ `SimSun` 字体
- 上游：MinerU（`ingest_mineru.ps1` 或等价）

## 一键端到端

```powershell
cd skills/pdf-exam-pipeline
python scripts/run_e2e.py `
  --md "path/to/mineru/auto/*.md" `
  --yaml output/questions.yaml `
  --out output/paper.pdf `
  --revise-q1
```

`--revise-q1`：仅替换第 1 题为内置二重积分题，第 2–5 题保持 MinerU 解析结果。

## 分步

| 步骤 | 模块 | 说明 |
|------|------|------|
| 解析 | `lib/parse_md.py` | MinerU MD → `questions.yaml`（5 题、meta、choice_layout） |
| 改题 | `lib/revise_question.py` | 按 `q_id` 只改一题 |
| 排版 | `templates/exam-zh.tex.j2` | 浙江外国语学院页眉、装订线、记分表、行内/多行选项 |
| 构建 | `lib/build_paper.py` | YAML → tex → xelatex → PDF |
| 验证 | `lib/verify.py` | 锚点标记 + 题数 + PDF 体积 |

## 测试

```powershell
cd skills/pdf-exam-pipeline
python -m unittest tests.test_parse -v
```

## Pilot 集成

`features/research/pdf-math-exam-to-latex-skill-survey/pilot/` 下脚本委托本 skill：

- `parse_md_to_yaml.py`
- `build_paper.py`

## 产出物路径（feature 标准）

| 文件 | 路径 |
|------|------|
| YAML | `pilot/questions/*.yaml` |
| PDF | `pilot/output/paper-*.pdf` |
