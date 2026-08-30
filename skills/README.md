# Skills

`skills/` 只保存有真实入口、可执行且需要随项目版本化的工作流。每个 skill 以 `SKILL.md` 为权威入口；运行前先读入口，不从生成配置副本执行。

当前共 8 个：

| Skill | 用途 | 定位 |
|---|---|---|
| [`gitsync/`](gitsync/SKILL.md) | 安全同步 Git 仓库与本仓登记的 repos | 核心 |
| [`obsidian-knowledge/`](obsidian-knowledge/SKILL.md) | 经 Obsidian Local REST API 创建、整理、审查知识库 | 核心 |
| [`pm/`](pm/SKILL.md) | 梳理和维护跨仓 feature spec 与验收标准 | 协作 |
| [`review/`](review/SKILL.md) | 多角色技术方案评审 | 协作 |
| [`grilling/`](grilling/SKILL.md) | 逐项追问并压力测试决策 | 协作 |
| [`smart-commit/`](smart-commit/SKILL.md) | 提交前分类与敏感信息检查 | 协作 |
| [`feidex/`](feidex/SKILL.md) | 本地飞书与 Codex / Claude Code 桥接 | 个人可选 |
| [`windows-c-drive-cleanup/`](windows-c-drive-cleanup/SKILL.md) | Windows 磁盘只读审计及授权后清理 | 个人可选 |

## 约束

- 文档中不得引用不存在的 skill。
- 密钥、缓存、查询结果和本机配置不得提交。
- `knowledge/**` 只能由 `obsidian-knowledge` 经 Local REST API 访问；任何 skill 都不得直接扫描或修改 vault。
- 工具专属适配文件由 `onecxt adapt` 本地生成，不复制回 `skills/`。
- `.agents/skills/` 只保存 Codex 的薄发现入口；工作流权威内容仍在 `skills/`。
- 新增或删除 skill 时同步更新本表和 `AGENTS.md` 中必要的路由。
