# AGENTS.md — Repository Guide

本仓是面向数学科研的 one-context 控制面。先确认事实来源，再修改；不要从旧生成配置推断当前结构。

## 权威来源

- `packages/one-context/`：`onecxt` / `one_context` 实现，CLI 改动只在这里完成。
- `meta/repos.yaml`：子仓 URL、路径、`id` 与别名。
- `meta/workspaces.yaml`：工作区；默认科研工作区为 `math-research`。
- `meta/profiles.yaml`、`meta/agents.yaml`：工具无关的行为与角色配置。
- `features/`：跨仓规格与评审记录；索引只列真实存在的目录。
- `skills/`：可执行工作流，以各目录的 `SKILL.md` 为入口。
- `docs/architecture.md`：当前架构与边界。
- `knowledge/`：个人 Obsidian vault submodule，不是 Agent 指令层。

## Skill routing

请求命中以下工作流时，必须先读对应 `SKILL.md`：

| 意图 | 入口 |
|---|---|
| Git 同步、拉取远端且保留本地改动 | `skills/gitsync/SKILL.md` |
| 知识库、Obsidian 笔记、整理或审查 vault | `skills/obsidian-knowledge/SKILL.md` |
| 本仓 `features/` 下的 PM 立项、PRD、需求梳理或 feature spec | `skills/pm/SKILL.md` |
| 多角色技术方案评审 | `skills/review/SKILL.md` |
| 逐项追问并压力测试决策 | `skills/grilling/SKILL.md` |

其余实际可用 skill 见 `skills/README.md`。不存在的 skill 不得写入路由、模板或 Agent 配置。

## 数学科研优先级

- 论文、证明与引用事实优先准确性和可追溯性。
- 代码与可视化改动应留最小可运行验证。
- 跨仓链接使用 `meta/repos.yaml` 中的仓库 `id`，不要猜路径。
- 研究原件、教学材料和个人输出不得因仓库整理而直接删除；先迁移到所属子仓或本地归档。

## Obsidian API-only

`knowledge/**` 笔记只能经 Obsidian Local REST API（`https://127.0.0.1:27124`）访问。禁止使用文件系统 Read/Write/Edit/Grep、`rg` 或脚本遍历 vault。

唯一允许直接修改的是 skill 自身文件：

- `skills/obsidian-knowledge/SKILL.md`
- `skills/obsidian-knowledge/playbooks/**`
- `skills/obsidian-knowledge/references/**`
- 本地且被忽略的 `skills/obsidian-knowledge/api-key.txt`

没有 API key 时，报告阻塞，不以文件系统访问降级。

## 生成配置

`.claude/`、`.cursor/`、`.hermes/`、`.openclaw/`、`CLAUDE.md` 与 `.hermes.md` 是 `onecxt adapt` 的本地输出，不是权威来源，不提交、不手改。

## 修改后验证

- 清单：`python -m one_context doctor`
- 测试：`python -m pytest packages/one-context/tests -q`
- Diff 卫生：`git diff --check`

默认输出简短直接。破坏性操作、发布、推送及外部写入必须有明确授权。
