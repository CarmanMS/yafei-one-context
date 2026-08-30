> ⛔ 本 playbook 所有 vault 操作必须走 Obsidian Local REST API（`curl → https://127.0.0.1:27124`）。禁止用 Read/Write/Edit/Grep 直接访问 `knowledge/` 笔记文件——详见主 `SKILL.md`「⛔ 硬性约束」。

# Playbook: audit

**子命令**：`/obsidian-knowledge check [--fix]`

**定位**：快速、本地、同步的静态规则扫描。秒级完成。与 `/review`（深度、逐文档 subagent、含 HTTP 检查）互补。

**前置**：读完主 `SKILL.md`。本 playbook 对 vault 笔记的**所有读取必须走 Obsidian Local REST API**（`curl GET → https://127.0.0.1:27124`）。**禁止** `find`/`Glob`/`Grep`/`Read` 直接扫 `knowledge/` 磁盘文件——违反 SKILL.md「⛔ 硬性约束」。

---

## 检查范围

`knowledge/` 全量 `.md` 文件，**排除**：
- `README.md`（说明文件）
- `_meta/`（HOME.md、命名与归档规则.md、插件建议.md、templates/）
- 各域 `_MOC.md`（地图页，手动维护）

---

## 规则清单

| # | 规则 | 严重 | 可修 | 说明 |
|---|------|------|------|------|
| C1 | 中文自然命名 | ERROR | ❌ | 文件名应见名知义的中文/数字；**禁止** kebab-case 与纯英文（日志类 `YYYY-MM-DD.md` 例外） |
| C2 | frontmatter 最小三字段 | ERROR | 部分 | `type` / `status` / `created` 必填；不能可靠推断的值交由用户确认 |
| C3 | 正文 ≥ 20 行 | WARN | ❌ | 不含来源信息块和空行 |
| C4 | 归档不出领域 | ERROR | ✅ | `status: archived` 或位于 `_archive/` 的笔记，必须仍在原领域内（无全局归档目录） |
| C5 | 顶层只放领域 | ERROR | ✅ | 顶层目录必须是 `00-inbox` / `NN-领域` / `_meta`；其他需迁移进最近领域 |
| C6 | 同领域无重复标题 | WARN | ❌ | 同领域内标题唯一 |
| C7 | 标签两级且以领域开头 | ERROR | ✅ | frontmatter YAML 值用 `科研/...` `教学/...` `家庭/...`，不带 `#`；删除非法标签 |
| C8 | 笔记至少 1 个 wikilink | WARN | ❌ | 排除 Inbox 随手记 |

**严重级别**：
- ERROR：必须处理；`--fix` 只自动执行标为 ✅ 的确定性修复，标为“部分”的字段先让用户确认
- WARN：建议修复，`--fix` 不自动处理，需用户决策

---

## 执行流程

```
1. 经 API 递归列出 vault 全部 `.md`（遍历文件夹：`GET /vault/<dir>/` → 对子文件夹递归），应用排除规则（`README.md` / `_meta/` / `_MOC.md`）
2. 对每个文件：
   a. 解析 frontmatter（YAML）
   b. 逐条规则检查
   c. 收集问题
3. 汇总输出报告
4. 若 --fix：对 ERROR 且可修的规则执行修复
```

---

## 输出格式

```
📋 知识库规范检查报告

扫描文件数：42
通过：35 | 警告：5 | 错误：2

━━━ ❌ ERROR (2) ━━━

  knowledge/10-科研/算子空间理论/operator-space.md
    [C1] 文件名应为中文自然命名（如：算子空间笔记.md），禁止 kebab-case
    [C2] 缺少 created 字段

  knowledge/20-教学/某笔记.md
    [C5] 顶层出现非领域目录，应迁移进 20-教学/ 下

━━━ ⚠️ WARN (5) ━━━

  knowledge/30-家庭/运动/游泳.md
    [C8] 笔记正文无 wikilink

  ...
```

---

## `--fix` 自动修复

> ⛔ **修复也必须走 API**：所有写操作通过 `curl -X PUT/PATCH/DELETE → https://127.0.0.1:27124/vault/...` 完成。**禁止** `git mv` / 直接写盘 / `Edit` 工具改 `knowledge/` 笔记。移动 = PUT 新路径 + DELETE 旧路径；改 frontmatter/标签 = PUT 整篇（含 `---` 块）。

仅修复 ERROR 且标记为可修的规则：

| 规则 | 修复动作 |
|------|---------|
| C2 | 仅补全能够从内容确认的 `type` / `status`；缺少 `created` 时不得从文件 mtime 推断，用户确认后才可写入 today |
| C4 | 将跨域归档的笔记移回原领域 `_archive/`，或仅设 `status: archived` |
| C5 | 经 API 将顶层非法目录内的笔记逐篇移动到最近领域目录 |
| C7 | 删除非法标签（frontmatter 仅保留 `领域/子主题` 形式，不带 `#`） |

**C1 不自动修复**：重命名为中文自然名需语义理解，标记为 ERROR 但留给人工处理。
**修复前必须展示预览，用户确认后才执行。**

### C5 修复的特殊处理

移动文件时：
1. 更新能够确认的 frontmatter；无法确认的 `created` 保持待处理
2. 经 API `PUT` 新路径并校验，再 `DELETE` 旧路径
3. 更新源和目标 `_MOC.md`
4. 扫反向链接（`[[旧路径]]`），逐篇 GET 最新全文、内存精确替换、PUT、GET 校验

---

## 实现示例

```bash
# 扫描所有 .md（全部经 API，禁止直接扫磁盘）
# 1) 递归列出（示例：用 curl 遍历文件夹，自行实现递归）
curl -sf -H "$AUTH" "https://127.0.0.1:27124/vault/"           # 顶层
curl -sf -H "$AUTH" "https://127.0.0.1:27124/vault/00-inbox/"  # 某域
# 2) 取单篇内容（API 读取，非 Read 工具）
curl -sf -H "$AUTH" "https://127.0.0.1:27124/vault/00-inbox/<笔记>.md"
# 3) 对内容套 C1-C8（下方 C1 示例，内容来自上一步 API 返回值）
basename=$(basename "$f" .md)
if echo "$basename" | grep -qE "^[a-z0-9-]+$" && ! echo "$basename" | grep -qE "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"; then
  echo "[C1] $f （应为中文自然命名）"
fi
# 解析 frontmatter 用 python/yq 处理 API 返回的文本（仍来自 API，非磁盘文件）
```

---

## 约束

- `--fix` 仅自动执行标为 ✅ 的 ERROR 修复；C1 与 C2 中无法确认的字段留给人工
- 修复前必须展示预览
- C5 修复涉及 API move + `_MOC.md` 更新 + 反向链接扫描，必须完整执行
- C7 修复只删除非法标签，不添加新标签
- 不修改文件正文内容，只修 frontmatter/目录/标签
