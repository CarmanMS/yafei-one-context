---
name: pm
description: 梳理、创建、评审或归档本仓 features/ 下的跨仓需求规格，并维护范围、非目标、验收标准、repo/workspace id 与 INDEX 一致。用于要求在本仓进行 PM 立项、PRD、需求梳理或 feature spec 工作；不用于通用产品咨询、实现、技术设计、代码评审或 Obsidian vault。
---

# PM

把请求整理成最小、可验证、可追溯的 feature spec；停留在需求层，不代替实现或技术决策。

## 事实来源

开始前读取：

- `AGENTS.md`
- `features/README.md`
- `features/_template/spec.md`
- `features/INDEX.md`
- `meta/repos.yaml`
- `meta/workspaces.yaml`
- 已存在的目标 feature 文件（如适用）

只按当前权威来源判断结构，不从工具生成配置或旧历史反推规则。不得通过文件系统访问 `knowledge/**`；确需使用 Obsidian 时，改走 `skills/obsidian-knowledge/SKILL.md` 的 API-only 流程。

## 工作方式

1. 先区分只读梳理与仓库写入。分析、评审或讨论需求时默认不改文件；只有用户明确要求创建、更新或归档 feature 时才写入。
2. 明确背景与问题、目标与非目标、用户场景、相关 workspace/repo `id`、验收标准、风险、隐私、可复现要求、开放问题及实现落点。只有会实质改变范围、category 或实现仓的缺失决策才追问；其余内容标为假设或待定。
3. 新建 feature 时以 `features/_template/spec.md` 为骨架，默认只创建所需目录和 `spec.md`，并同步 `features/INDEX.md`。不要预建技术设计、测试、评审或交付文档。
4. repo 与 workspace 只使用 manifest 中可解析的稳定 `id`；不要猜路径、分支、PR、引用或架构决策。没有明确实现仓时，spec 保留为空并在开放问题说明；仅在 `features/INDEX.md` 的 `primary_repo_id` 列填 `—`。
5. 数学科研事项须区分已证明结论、猜想与待核实断言，并记录文献来源和版本、符号与假设、证明依赖及计算实验的最小复现命令。模型生成内容不得当作证明或已核实引用。
6. 写后检查目录名、frontmatter `id` 与索引一致，索引只指向真实目录，并执行 `AGENTS.md` 当前列出的修改后验证。

## 边界

- 不编写实现代码、技术方案、测试或发布方案。
- 归档默认只更新状态；不移动或删除研究原件、教学材料或个人输出。
- 不修改生成配置，不创建分支、commit、push、PR、发布或执行其他外部写入，除非用户另行明确授权。
- 保留目标文件中的无关内容和用户已有改动。
