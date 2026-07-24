# Claude Memory · 镜像备份（非单源）

**单源真实路径**：`~/.claude/projects/-Users-superno-Documents-code-creative-one-context/memory/`

Claude Code 运行时**只读单源**，不读本目录。本目录纯属"防硬盘挂"的 git 备份。

## 同步约定

- 写 memory 时**先写单源**，再手动 `cp` 到此处 commit
- 单源被 Claude 自动改时（你看到 memory 变了），及时 `cp -r` 同步到此处 commit
- 简单同步：`rsync -av ~/.claude/projects/-Users-superno-Documents-code-creative-one-context/memory/ knowledge/claude-memory/`（保留 README.md，加 `--exclude README.md` 防被冲掉）

## 当前已存（2026-05-30）

- `cost-no-limit.md`（feedback）
- `subagent-task-tool-registry.md`（reference）
- `trust-but-verify-subagent.md`（feedback）
- `skill-eval-runner-phase1-done.md`（project）
- `MEMORY.md`（索引）

详见各 `.md` frontmatter `description` 字段。
