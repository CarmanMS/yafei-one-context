# 技术方案 — 算子空间论文表述规范（范本蒸馏 + Skill）

关联：`spec.md`

## 上下文与约束

- **范本**：`repos/research/ai/archive/20201107/revisedoperatorspace.tex`（体积大，留在 `repos/`；knowledge 只存蒸馏条文与极短摘录）。
- **规范**：`knowledge/references/` 文档须符合 `one-context-conventions.md` 的来源信息要求；对外转载时注意原版版权。
- **Skill**：遵循 `skills/*/SKILL.md` + frontmatter；工具中立，不出现特定 IDE 指令语法。

## 方案概览

| 构件 | 路径（拟定） | 职责 |
|------|----------------|------|
| 写作规范 | `knowledge/references/operator-space-paper-prose.md` | 风格规则、反模式、与范本的关系、可选 2–3 句以内摘抄示例 |
| Skill | `skills/operator-space-paper-prose/SKILL.md` | 触发条件、阅读顺序、自检清单、与 kb 的固定引用路径 |
| 适配输出 | `.cursor/rules/skill-operator-space-paper-prose.mdc` 等 | 由 `onecxt adapt` 生成，**不手改** |

## 接口与数据

- **输入**：用户草稿、章节要点、或「改写得更像教材」类指令。
- **输出**：符合规范的 LaTeX 自然语言片段或纯英文段落（不在 Skill 内执行编译）。
- **依赖**：代理需能 `Read` knowledge 文件；范本 `.tex` 按需分段读取。

## 依赖与风险

- **风险**：过度摘抄范本进入 knowledge → 版权与仓库体积；缓解：只保留规则化描述与必要时 ≤3 行「最小必要」引用并注明出处。
- **风险**：Skill 与 kb 路径不一致 → 代理漏读；缓解：Skill 内写死相对路径并在一处 `tech_design` / `spec` 对照。

## 迁移与回滚

- 若重命名 knowledge 文件：同步改 Skill 内路径与（如有）`meta/workspaces.yaml` / agent `knowledge` 列表。
- 回滚：删除 skill 目录与 knowledge 文件，移除 adapt 生成规则后重新 adapt。
