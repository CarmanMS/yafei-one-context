# 测试报告 — pdf-math-exam-to-latex-skill-survey

**日期**：2026-05-29  
**环境**：Windows，Python 3.11，MiKTeX 2.9（CTeX），`xelatex` 可用  
**样张**：`2023-2024-2高等数学C（二）A卷.pdf` → MinerU MD（`pilot/output/mineru/.../auto/*.md`）

---

## 验收结果

| 编号 | 检查项 | 结果 | 说明 |
|------|--------|------|------|
| V1 | MinerU 安装 | **通过** | 此前已验证；本机 ingest 产出真实 MD |
| V2 | 真实 PDF→MD | **通过** | MinerU 解析 C（二）A 卷第 1 页，含 5 道选择题 |
| V3 | MD→YAML | **通过** | `skills/pdf-exam-pipeline/lib/parse_md.py` 解析 5 题；`pilot/parse_md_to_yaml.py` 委托 skill |
| V4 | 单题改题 | **通过** | `ai_revise_questions.py --q-id q1` 仅替换第 1 题为二重积分，2–5 题不变 |
| V5 | PDF 构建 | **通过** | `pilot/output/paper-c2-e2e.pdf`，`xelatex` 无致命错误 |
| V6 | 版式锚点 | **通过（自动）** | `verify_paper.py`：页眉/装订线/MATH1029/记分表/行内选项锚点齐全 |

---

## 端到端命令

```powershell
cd features/research/pdf-math-exam-to-latex-skill-survey/pilot

python parse_md_to_yaml.py --md "output/mineru/2023-2024-2高等数学C（二）A卷/auto/2023-2024-2高等数学C（二）A卷.md" --out questions/parsed-from-md.yaml
python ai_revise_questions.py --in questions/parsed-from-md.yaml --out questions/page1-c2-a-v2.yaml
python build_paper.py --input questions/page1-c2-a-v2.yaml --out output/paper-c2-e2e.pdf
python verify_paper.py --tex output/paper.tex --pdf output/paper-c2-e2e.pdf --yaml questions/page1-c2-a-v2.yaml
```

或使用 skill 一键脚本：

```powershell
cd skills/pdf-exam-pipeline
python scripts/run_e2e.py --md "<path-to-mineru.md>" --revise-q1 --out output/e2e-paper.pdf
python -m unittest tests.test_parse -v
```

---

## 已知限制

1. **版式非像素级**：模板对齐 MinerU layout 第 1 页结构（页眉、装订线、表格、题号、A/B/C/D），字体/行距与原 PDF 可能仍有细微差异。  
2. **公式清理**：MinerU 碎裂 LaTeX 经 `formula_cleanup.py` 规整；复杂式子需人工抽检。  
3. **第 2 题选项**：部分选项无 `$` 包裹（如 `1`、`-1`），排版可接受。  
4. **输出文件占用**：若 `paper-c2-a-v2.pdf` 被 PDF 阅读器锁定，`build_paper.py` 会提示写入 `-new` 副本。

---

## 结论

**真实样张闭环已跑通**：MinerU MD → YAML（自动解析 5 题）→ 仅改 q1 → 原卷版式 PDF → 自动验证。  
Skill 沉淀于 `skills/pdf-exam-pipeline/`（`SKILL.md` + lib + 模板 + 单测）。
