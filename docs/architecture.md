# Architecture

## 定位

yafei-one-context 是面向个人数学科研的本地控制面。它连接多个独立 Git 仓库、一个个人 Obsidian vault 和若干 AI 工具，但不合并各仓历史，也不把私人知识复制到工具配置中。

## 层次

### 1. Registry

`meta/` 是机器可读事实来源：

- `repos.yaml`：远端、稳定 repo id 与本地路径
- `workspaces.yaml`：跨仓任务视图；当前主视图是 `math-research`
- `profiles.yaml`：工具无关的行为策略
- `agents.yaml`：少量明确角色及其可加载上下文

### 2. Working copies

`repos/` 保存独立克隆并由 `onecxt sync` 管理。本仓不跟踪其内容。跨仓引用使用 repo id，不使用猜测的绝对路径。

### 3. Knowledge vault

`knowledge/` 是 Git submodule 固定的个人 Obsidian vault。它是私人研究数据，不是 Agent 指令层。

所有笔记访问必须经过 Obsidian Local REST API 和 `skills/obsidian-knowledge/SKILL.md`。解析器、doctor、context export 与 adapter 都不得遍历、读取或内联 `knowledge/**`。

### 4. Features and skills

`features/` 保存真实存在的跨仓事项；`INDEX.md` 是目录事实的索引，不是历史愿望清单。

`skills/` 保存可执行工作流。入口是各自的 `SKILL.md`，运行时缓存和密钥留在本机。

### 5. CLI

`packages/one-context/` 提供 `onecxt`：

- 读取与校验清单
- 同步登记仓库
- 列出 repo、workspace、profile 与 agent
- 组装允许的上下文
- 生成工具适配输出

CLI 必须返回可用于自动化的退出码，并在 Windows、macOS 和 Linux 上保持同一语义。

### 6. Adapters

Adapter 只翻译 `meta/`、`docs/`、`features/`、`skills/` 等允许来源，不拥有业务事实。

`.claude/`、`.cursor/`、`.hermes/`、`.openclaw/` 及对应根入口是本地生成物，默认不进入 Git。修改源文件后重新运行 `onecxt adapt`。

## 数据流

```text
meta + docs + features + skills
              │
              ├── onecxt doctor / context export
              └── onecxt adapt ──> local tool configs

Obsidian client ── Local REST API ──> knowledge submodule
```

两条路径不交叉：adapter 不直接消费 vault，vault 工作流也不修改框架配置。

## 专业边界

- 清单和文档必须指向真实路径。
- 生成物、缓存、个人会话和凭证不提交。
- 研究原件在所属子仓或私人归档中保存。
- 未通过校验和测试的能力不宣称稳定。
- 新层、新角色或新依赖只在出现真实使用者后增加。
