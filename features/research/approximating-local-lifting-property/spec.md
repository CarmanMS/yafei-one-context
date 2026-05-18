---
id: approximating-local-lifting-property
title: Approximating Local Lifting Property
status: draft
category: research
primary_repo_id: ""
owner: ""
updated: "2026-05-11"
---

# 概述

英文稿 **The Approximating Local Lifting Property for $p$-Operator Spaces**（ALLP / $\lambda$-$p$-LLP 等价与近似 $p$-内射性等），写作中与修订同步。

本目录 `paper/p_ALLP.tex` 为便于伞仓跟踪而保存的副本；若你还在 `repos/research/ai/` 下放有同名 `.tex`，编辑后需 **双向同步**，并在 **实际编译的那份** 上运行 `pdflatex`（本仓库 glob 显示当前仅有 `features/.../paper/p_ALLP.tex` 一份源文件）。

**硬性约定（避免「tex 已改、PDF 看起来没改」）**

- 修改 `paper/p_ALLP.tex` 后，**同一轮任务内**应运行 `paper/compile-pdf.ps1`（脚本结束会打印 `p_ALLP.pdf updated:` 与磁盘时间戳）；除非用户只要改源码、明确不要求 PDF。
- 若编辑器里 PDF 仍是旧句：**关掉该 PDF 标签页再打开**同一路径文件，或到外置阅读器打开 `paper/p_ALLP.pdf`。

**改 `.tex` 后 PDF「没变」的常见原因**

1. **未重新编译**：LaTeX 不会自动更新 `.pdf`。在 `paper/` 目录执行 `.\compile-pdf.ps1`，或 `pdflatex -interaction=nonstopmode p_ALLP.tex`（建议连跑两遍以稳定交叉引用）。
2. **IDE 内嵌 PDF 预览缓存**：Cursor / VS Code 有时仍显示旧渲染；请 **关掉 PDF 标签页再打开**，或用 Sumatra / Acrobat 直接打开磁盘上的 `paper/p_ALLP.pdf`。

# 目标与非目标

## 目标

- 完成并定稿上述论文的 TeX 与 PDF。
- 与 `features/research/operator-space-paper-writing-style/` 等表述规范对齐（如需）。

## 非目标

- 不在此 feature 内替代 `repos/research/ai` 的 Git 版本历史（仍以研究目录仓库为准）。

# 验收标准

- [ ] `paper/p_ALLP.tex` 与既定主副本一致或可解释的差异说明。
- [ ] PDF 可由 `pdflatex` 无错误编译（建议在 `repos/research/ai/papers/` 执行）。

# 实现落点（必填）

- **仓库 id**（`meta/repos.yaml`）: —（研究稿路径未单独注册时用 `—`）
- **分支 / PR**: —
- **主要路径或模块**:
  - `features/research/approximating-local-lifting-property/paper/p_ALLP.tex`（本 feature 副本）
  - `repos/research/ai/p_ALLP.tex`
  - `repos/research/ai/papers/p_ALLP.tex`

# 关联

- **Workspace**（`meta/workspaces.yaml` id，如有）: —
- **其他需求目录**: `features/research/p-operator-space-injective-papers/`、`features/research/operator-space-paper-writing-style/`

# 开放问题

- **Lee (2015) 误读澄清**：Lee 仅证明了存在 $SQ_p$ 空间 $E$ 使得 $B(\tilde{E})$ 不是 $p$-内射的，**并未证明** $B(L_p)$ 或 $B(\ell_p)$ 不是 $p$-内射的。$B(\ell_p)$ 的 $p$-内射性至今仍是**开放问题**。
- **等价关系 $B_p(\ell_p)$ $p$-内射 $\iff T_p(\ell_p)$ $p$-LLP**：在纠正了 Lee (2015) 的误读后，这一对空间的内射性/提升性质等价关系重获生命力，证明此等价且两边成立是该领域的重大目标。
- **潜在研究路径**：基于 $\ell_p$ 特殊刚性（$T_p(\ell_p)=\mathcal{K}_p(\ell_p)^*$ 与 $B_p(\ell_p)=\mathcal{K}_p(\ell_p)^{**}$，有限秩稠密与标准基），有望绕开一般 $p$-算子空间的对偶商映射障碍，直接建立该等价关系。
