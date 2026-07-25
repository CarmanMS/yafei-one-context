---
name: gitsync
description: Use when you need to fetch and pull latest code from remote, sync local branch with upstream, or update codebase before starting work. Includes submodule and virtual monorepo sub-repos sync.
---

# Git Sync (Fetch & Pull)

## Current Status
Current branch: !`git branch --show-current`
Remote tracking: !`git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo "No upstream configured"`
Local changes: !`git status --porcelain 2>/dev/null | head -5 || echo "Clean"`

## Core Principle: Compare Before Fetch

**先比对本地缓存的远程引用，再决定是否 fetch。** 避免大仓库不必要的网络传输。

```
Local HEAD == cached origin/HEAD → Already up to date (skip fetch)
Local HEAD != cached origin/HEAD → Fetch + pull
Fetch fails / timeout           → Report error, continue next repo
```

## SSH Proxy Auto-Bypass

`~/.ssh/config` 可能为 `github.com` 配了 SOCKS5 代理（如 `ProxyCommand nc -X 5 -x localhost:57517`），代理端口挂了会导致 SSH 连接失败或无限卡住。

**所有 git remote 使用 SSH 协议（`git@github.com:`）的仓库，必须带环境变量：**

```bash
export GIT_SSH_COMMAND="ssh -o ProxyCommand=none"
```

这样绕过 `~/.ssh/config` 的坏代理，直连 github.com。SSH 认证本身没问题（key 认证不依赖代理）。

## Sync Process

### Step 1: Sync Main Repo

```bash
cd <project-root>

CURRENT_BRANCH=$(git branch --show-current)
UPSTREAM=$(git rev-parse --abbrev-ref @{upstream} 2>/dev/null)

if [ -z "$UPSTREAM" ]; then
    echo "ERROR: No upstream branch configured for $CURRENT_BRANCH"
    echo "Run: git branch --set-upstream-to=origin/$CURRENT_BRANCH $CURRENT_BRANCH"
    exit 1
fi

LOCAL_HEAD=$(git rev-parse HEAD)
CACHED_REMOTE=$(git rev-parse "$UPSTREAM" 2>/dev/null || echo "unknown")

echo "=== 主仓库 ($CURRENT_BRANCH) ==="
echo "  Local:  ${LOCAL_HEAD:0:8}"
echo "  Remote (cached): ${CACHED_REMOTE:0:8}"

# Already up to date? Skip fetch entirely.
if [ "$LOCAL_HEAD" = "$CACHED_REMOTE" ] && [ "$CACHED_REMOTE" != "unknown" ]; then
    echo "  ✓ Already up to date (local matches cached remote)"
    # Light fetch to confirm (with timeout)
    timeout 15 bash -c 'GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch origin "$CURRENT_BRANCH" 2>&1' >/dev/null
    NEW_REMOTE=$(git rev-parse "$UPSTREAM" 2>/dev/null)
    if [ "$LOCAL_HEAD" = "$NEW_REMOTE" ]; then
        echo "  ✓ Confirmed up to date"
    else
        echo "  Remote changed: ${NEW_REMOTE:0:8}, pulling..."
        # Stash if dirty
        STASHED=false
        if git status --porcelain | grep -q .; then
            git stash push -m "gitsync-auto" >/dev/null 2>&1
            STASHED=true
        fi
        GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git pull --ff-only 2>&1
        $STASHED && git stash pop >/dev/null 2>&1
    fi
else
    # Need to fetch
    echo "  Fetching..."
    STASHED=false
    if git status --porcelain | grep -q .; then
        git stash push -m "gitsync-auto" >/dev/null 2>&1
        STASHED=true
    fi
    GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch origin "$CURRENT_BRANCH" 2>&1
    NEW_REMOTE=$(git rev-parse "$UPSTREAM" 2>/dev/null)

    if [ "$LOCAL_HEAD" = "$NEW_REMOTE" ]; then
        echo "  ✓ Already up to date"
    elif git merge-base --is-ancestor "$LOCAL_HEAD" "$NEW_REMOTE" 2>/dev/null; then
        GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git pull --ff-only 2>&1 && echo "  ✓ Synced"
    else
        echo "  ⚠️ Diverged — needs manual resolution"
    fi
    $STASHED && git stash pop >/dev/null 2>&1
fi
```

### Step 2: Sync Git Submodules

!`test -f .gitmodules && grep -E '^\\[submodule' .gitmodules | sed 's/\\[submodule "//;s/"\\]//' | while read sub; do echo "=== $sub ==="; cd "$sub" 2>/dev/null && REMOTE=$(git rev-parse --abbrev-ref @{upstream} 2>/dev/null) && if [ -n "$REMOTE" ]; then LOCAL=$(git rev-parse HEAD); REMOTE_HEAD=$(git rev-parse $REMOTE); echo "  Local:  ${LOCAL:0:8}"; echo "  Remote: ${REMOTE_HEAD:0:8}"; if [ "$LOCAL" != "$REMOTE_HEAD" ]; then GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch --all && GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git pull --ff-only; else echo "  ✓ Already up to date"; fi; else echo "  ⚠️ No upstream configured"; fi || echo "✗ FAILED"; cd - > /dev/null; done || echo "No submodules"`

### Step 3: Sync Virtual Monorepo Sub-repos

对 `repos/` 下每个仓库：

1. **先比对**本地 HEAD 与缓存的 `origin/<branch>` — 相同则跳过 fetch（仅做确认性轻 fetch）
2. **带 GIT_SSH_COMMAND** 绕过坏代理
3. **带超时** 防止大仓库 fetch 卡死
4. **有未提交变更** → stash → pull → pop

```bash
find repos -name ".git" -type d -maxdepth 3 2>/dev/null | sort | while read gitdir; do
  repo=$(dirname "$gitdir")
  branch=$(git -C "$repo" branch --show-current 2>/dev/null)
  upstream=$(git -C "$repo" rev-parse --abbrev-ref @{upstream} 2>/dev/null)

  if [ -z "$upstream" ]; then
    echo "=== $repo === ⚠️ No upstream"
    continue
  fi

  LOCAL=$(git -C "$repo" rev-parse HEAD)
  CACHED_REMOTE=$(git -C "$repo" rev-parse "$upstream" 2>/dev/null || echo "unknown")

  echo -n "=== $repo ($branch) === "

  # Stash if dirty
  STASHED=false
  if git -C "$repo" status --porcelain | grep -q .; then
    git -C "$repo" stash push -m "gitsync-auto" >/dev/null 2>&1
    STASHED=true
  fi

  # If local matches cached remote, do light confirm fetch with timeout
  if [ "$LOCAL" = "$CACHED_REMOTE" ] && [ "$CACHED_REMOTE" != "unknown" ]; then
    timeout 20 bash -c 'export GIT_SSH_COMMAND="ssh -o ProxyCommand=none"; git -C "'"$repo"'" fetch origin "'"$branch"'" 2>&1' >/dev/null 2>&1
    NEW_REMOTE=$(git -C "$repo" rev-parse "$upstream" 2>/dev/null)
    if [ "$LOCAL" = "$NEW_REMOTE" ]; then
      echo "✓ Already up to date"
      $STASHED && git -C "$repo" stash pop >/dev/null 2>&1
      continue
    fi
    # Remote changed, fall through to pull
  else
    # Need full fetch
    timeout 30 bash -c 'export GIT_SSH_COMMAND="ssh -o ProxyCommand=none"; git -C "'"$repo"'" fetch origin "'"$branch"'" 2>&1' >/dev/null 2>&1
    FETCH_EXIT=$?
    if [ $FETCH_EXIT -ne 0 ]; then
      echo "✗ Fetch failed/timeout"
      $STASHED && git -C "$repo" stash pop >/dev/null 2>&1
      continue
    fi
  fi

  # Pull if needed
  NEW_REMOTE=$(git -C "$repo" rev-parse "$upstream" 2>/dev/null)
  if [ "$LOCAL" = "$NEW_REMOTE" ]; then
    echo "✓ Already up to date"
  elif git -C "$repo" merge-base --is-ancestor "$LOCAL" "$NEW_REMOTE" 2>/dev/null; then
    GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git -C "$repo" pull --ff-only >/dev/null 2>&1
    echo "✓ Synced to ${NEW_REMOTE:0:8}"
  else
    echo "⚠️ Diverged"
  fi

  $STASHED && git -C "$repo" stash pop >/dev/null 2>&1
done
```

## Output Format

完成后以表格汇总：

| 仓库 | 状态 | 说明 |
|------|------|------|
| 主仓库 | ✓/⚠️/✗ | 结果 |
| repos/xxx | ✓/⚠️/✗ | 结果 |
| ... | ... | ... |

**状态说明**：
- ✓ Already up to date / Synced
- ⚠️ 警告（diverged / no upstream）
- ✗ 失败（fetch failed / timeout）

## Handling Failures

### Failure Type 1: Local Uncommitted Changes
**Error:** `error: Your local changes would be overwritten by merge`

**Solutions:**
```bash
# Option A: Stash changes, pull, then restore
git stash && git pull --ff-only && git stash pop

# Option B: Commit local changes first
git add -A && git commit -m "WIP: local changes"
```

### Failure Type 2: Divergent History (Not fast-forwardable)
**Error:** `fatal: Not possible to fast-forward, aborting`

**Solutions:**
```bash
# Option A: Rebase local commits on top of remote (cleaner history)
GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git pull --rebase

# Option B: Create merge commit (preserves branch history)
GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git pull --no-ff

# Option C: Reset to remote (DISCARD local commits - confirm first!)
GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch && git reset --hard @{upstream}
```

### Failure Type 3: Merge Conflicts (after rebase/merge)
**Error:** `CONFLICT (content): Merge conflict in <file>`

**Resolution Steps:**
1. List conflicted files: `git status`
2. Open each file and look for `<<<<<<<` markers
3. Resolve conflicts manually in editor
4. Stage resolved files: `git add <files>`
5. Complete: `git rebase --continue` (for rebase) or `git commit` (for merge)
6. If you want to abort: `git rebase --abort` or `git merge --abort`

### Failure Type 4: SSH Proxy 不可用导致连接失败
**Error:** `Connection closed by UNKNOWN port 65535` / SSH 卡住无响应 / `Could not read from remote repository`

**原因：** `~/.ssh/config` 为 `github.com` 配了 `ProxyCommand`（SOCKS5），代理端口已死。

**诊断：**
```bash
# 测试 SSH 直连
ssh -o ProxyCommand=none -T git@github.com
# 成功: Hi <user>! You've successfully authenticated...

# 检查 SSH 配置
grep -A3 "Host github.com" ~/.ssh/config
```

**解决方案：** 本技能所有 git 命令已内置 `GIT_SSH_COMMAND="ssh -o ProxyCommand=none"`，无需手动处理。如需全局临时生效：

```bash
export GIT_SSH_COMMAND="ssh -o ProxyCommand=none"
```

### Failure Type 5: HTTPS Remote 认证失败
**Error:** `fatal: Authentication failed for 'https://github.com/<owner>/<repo>/'`

**原因：** GitHub 已禁止密码认证，HTTPS 需要 token。

**方案 A — 切换到 SSH remote（推荐）：**
```bash
find repos -name ".git" -type d -maxdepth 3 2>/dev/null | sed 's|/.git$||' | while read repo; do
  url=$(git -C "$repo" remote get-url origin 2>/dev/null)
  if echo "$url" | grep -q "^https://github.com/"; then
    repo_path=$(echo "$url" | sed 's|https://github.com/||; s|\.git$||')
    git -C "$repo" remote set-url origin "git@github.com:${repo_path}.git"
    echo "$repo: switched to SSH"
  fi
done
```

**方案 B — 配置 GitHub credential helper + PAT**

### Failure Type 6: 大仓库 Fetch 超时
**Error:** fetch 命令长时间无输出

**原因：** 仓库体积大（>100M），SSH 传输慢。

**策略：**
1. **先比后 fetch** — 本地 HEAD 与缓存 remote 引用相同时，跳过 fetch（仅做轻量确认）
2. **设超时** — 对每个仓库的 fetch 设 20-30s 超时，超时则标记跳过
3. **不阻塞** — 单个子仓库超时不影响其他仓库同步

## Quick Reference

| Situation | Command |
|-----------|---------|
| Normal sync | `GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch origin <branch> && git pull --ff-only` |
| With local changes | `git stash && GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git pull --ff-only && git stash pop` |
| With local commits | `GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch origin <branch> && git pull --rebase` |
| Force merge | `GIT_SSH_COMMAND="ssh -o ProxyCommand=none" git fetch origin <branch> && git pull --no-ff` |
| Check all repo status | `find repos -name ".git" -type d \| while read d; do dir=$(dirname "$d"); echo "$dir: $(cd $dir && git status -s)"; done` |
| Abort rebase | `git rebase --abort` |
| Abort merge | `git merge --abort` |

## Git Safety Rules

- NEVER use `git pull --force` (doesn't exist)
- NEVER `git reset --hard` without user confirmation
- ALWAYS read error messages carefully before acting
- `--ff-only` fails safely - it won't create unexpected merge commits
- When in doubt, use `git stash` to save work before syncing
- ALWAYS use `GIT_SSH_COMMAND="ssh -o ProxyCommand=none"` to bypass stale SSH proxy

## Changelog

### 2026-06-13
- **核心改进：先比后 fetch** — 本地 HEAD 等于缓存远端引用时跳过 fetch，避免大仓库白传
- **内置 SSH proxy bypass** — 所有 git 命令统一带 `GIT_SSH_COMMAND="ssh -o ProxyCommand=none"`
- **fetch 超时保护** — 每个仓库 fetch 设 20-30s 超时，单仓库失败不阻塞全局
- 移除 Failure Type 4（fetch 无变化），逻辑已内置到主流程
- 合并旧 Failure Type 5（SSH Proxy）和 Type 6（HTTPS Auth），重编号

### 2026-05-26
- 添加 fetch 前后 commit hash 对比验证
- 使用 `git fetch <remote> <branch>` 替代 `fetch --all` 提高精确性
- 子仓同步添加 HEAD 对比检查
- 明确输出 "Already up to date" 或更新信息