---
name: smart-commit
description: 审查当前 Git 变更，按逻辑精确暂存并创建本地提交；仅在用户明确要求时推送。
---

# Smart Commit

用于用户明确要求提交当前工作时。目标是保留现有改动、避免敏感信息，并产出少量可独立理解的 commit。

## 1. 只读快照

先运行：

```bash
git status --short --branch
git diff --stat
git diff --cached --stat
git remote -v
```

再按需读取相关 diff。不要用 `git add -A` 掩盖未审查文件，也不要自动清理、移动或覆盖用户改动。

确认：

- 当前分支与 upstream
- 已暂存、未暂存、未跟踪和 submodule pointer 变化
- 变更是否混入 `.env`、密钥、个人会话、生成媒体或本地 adapter 输出
- 每组改动是否有对应验证

## 2. 仓库边界

通常可提交：

- `meta/`、`features/`、`skills/`、`docs/`
- `packages/one-context/`、`.github/`
- 根级项目文档和配置
- 已在子模块自身形成 commit 的 `knowledge` gitlink 变化

不得提交：

- `.env`、API key、token、浏览器或 Agent 会话
- `output/`、`.workbuddy/`、缓存、构建产物和独立 `repos/` 内容
- `.claude/`、`.cursor/`、`.hermes/`、`.openclaw/`、`CLAUDE.md` 等本地生成配置
- 尚未在知识子模块内形成 commit 的 vault 工作区变化

`knowledge/**` 笔记不得通过文件系统读取、搜索或暂存。外层只检查并提交已有的 submodule pointer；需要处理笔记时转交 `obsidian-knowledge`，并仅走 Local REST API。

发现错位、敏感或归属不明的文件时，先报告并等待决定；提交请求本身不授权删除、归档或重写历史。

## 3. 提交计划

按“能否独立解释和回滚”分组，而不是机械按目录拆分。通常 1–3 个 commit 足够。向用户简要列出：

- commit message
- 精确路径
- 验证结果
- 排除或阻塞项

若用户已经明确要求“把这些改动提交”，可在范围清晰且无风险项时直接执行该计划；范围不清或包含他人改动时先确认。

## 4. 精确执行

每组使用精确路径暂存：

```bash
git add -- <path>...
git diff --cached --check
git diff --cached --stat
git commit -m "<message>"
```

提交后复查：

```bash
git status --short --branch
git log -n 3 --oneline
```

规则：

- 不使用 `git reset --hard`、`git checkout --` 或 force push。
- 不自动添加固定 co-author、签名或作者身份。
- hook 失败时修复原因并重新验证，不用 `--no-verify` 绕过。
- 不修改 Git 全局配置。
- 未被纳入计划的变更保持原样。

## 5. 推送门控

本地 commit 不等于授权推送。只有用户明确要求 push / 推送时才执行：

```bash
git push
```

没有 upstream 时，先展示目标 remote 与 branch；确认无误后使用 `git push -u <remote> <branch>`。禁止默认推送到 `main`，禁止 force push。

## 6. 交付

报告 commit hash、message、包含范围、验证结果、未提交变更，以及是否推送。不要把敏感命中内容原样复制到报告。
