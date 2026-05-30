# Features index

在新建或归档需求时更新本表。`id` 建议与目录名 `features/<category>/<feature-id>/` 中的 `<feature-id>` 一致（或与 `spec.md` frontmatter 的 `id` 一致）。

| id | title | category | status | path | primary_repo_id |
| -- | ----- | -------- | ------ | ---- | --------------- |
| p-operator-space-injective-papers | p 算子空间 injective 文献研究 | research | draft | `features/research/p-operator-space-injective-papers/` | — |
| operator-space-paper-writing-style | 算子空间论文表述：范本蒸馏 + Skill | research | in_progress | `features/research/operator-space-paper-writing-style/` | — |
| approximating-local-lifting-property | Approximating Local Lifting Property | research | draft | `features/research/approximating-local-lifting-property/` | — |
| pdf-math-exam-to-latex-skill-survey | 数学试卷 PDF → LaTeX 能力调研（Skill / 工具 / 开源方案） | research | in_progress | `features/research/pdf-math-exam-to-latex-skill-survey/` | one-context |
| second-dual-local-properties | 算子空间局部性质与二重对偶（exactness、local reflexivity 等下降无提升律） | research | done | `features/research/second-dual-local-properties/` | — |
| completely-integral-corrigendum | Completely integral nuclearity 勘误与结构定理 | research | in_progress | `features/research/completely-integral-corrigendum/` | — |
| local-reflexivity-exactness | Local reflexivity 与 exactness（Effros--Ruan、Pisier 常数） | research | in_progress | `features/research/local-reflexivity-exactness/` | — |

**Columns**

- **primary_repo_id**: `meta/repos.yaml` 里条目的 `id`（或主实现仓库）；无则填 `—`。
- **path**: 相对 one-context 根目录的路径，用反引号包起来便于复制。
