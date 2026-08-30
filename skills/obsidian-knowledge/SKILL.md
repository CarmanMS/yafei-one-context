---
name: obsidian-knowledge
description: Obsidian 个人知识库（科研/教学/家庭 三领域）统一管理入口。创建/导入/整理/归类/去重/编译/审查/规范性检查，通过 Local REST API 维护 one-context knowledge vault 的 wikilinks、MOC、标签。取代原 kb / kb-compile / kb-review。
---

# Execution policy: API-first and API-only

This policy is mandatory for every operation involving `knowledge/**` notes.

1. Treat every `.md` file under `knowledge/` as an Obsidian-managed note, not as an ordinary repository file.
2. Before reading, searching, creating, editing, moving, renaming, or deleting a note, check the Local REST API at `https://127.0.0.1:27124/` and authenticate with the configured API key.
3. Use the Local REST API for both reads and writes: `/vault/{path}`, `/search/simple/`, `/search/`, `/open/{path}`, `/tags/`, and the corresponding mutation endpoints.
4. Do not use filesystem read/search/write tools on `knowledge/**`: no `Read`, `Grep`, `rg`, `Get-Content`, `cat`, `sed`, `Write`, `Edit`, `Set-Content`, or equivalent commands.
5. If the API is unavailable, stop the vault operation and report the exact blocker. Do not silently fall back to direct filesystem access. Only proceed with a non-vault operation, such as editing this skill's own files, when it is clearly outside `knowledge/**`.
6. A command or script that internally reads or writes vault files directly is also prohibited. A helper is allowed only when it uses the Local REST API for the vault operation.

## Mandatory decision sequence

For any request that mentions `knowledge`, `vault`, a note path, or Obsidian:

1. Identify whether the target is under `knowledge/**`.
2. If yes, check API availability and load the API key.
3. Read the relevant rules and notes through API calls only.
4. Perform the requested operation through API calls only.
5. Report the API endpoints used and any files changed. If API access failed, do not claim the operation was completed.

## Search and audit clarification

`check`, `review`, and other audit workflows must use API search/read operations whenever they inspect note content. Local filesystem tools may inspect only this skill's own definition files and non-vault repository metadata; they must never be used to inspect `knowledge/**` note contents.

This API-only policy overrides any older fallback wording elsewhere in this file or in a playbook. If the API is unavailable, stop and report the blocker; never silently downgrade to filesystem access.

# Obsidian Knowledge Vault Manager

> 统一管理入口。取代原 `kb` / `kb-compile` / `kb-review` 三个 skill。
> **架构**：`SKILL.md` 是 thin dispatcher，具体工作流拆到 `playbooks/`，schema 在 `references/`。扩展新工作流 = 加一个 playbook + 一条子命令。

**Vault 路径**：`<repo-root>/knowledge/`（git submodule，**不要**硬编码绝对路径）
**API 基址**：`https://127.0.0.1:27124`（HTTPS，**主用**）

> ⚠️ **运行环境约束**：
> 1. 某些沙箱不能访问本机回环地址。遇到 `HTTP 000` 时，改用产品提供的、已授权的本地执行通道；不要为此关闭其他安全保护。仍不可达就停止并报告。
> 2. `27124` 使用本机自签证书，因此仅对这些明确的 loopback 请求加 `curl -k`。不要在全局 `~/.curlrc` 中配置 `insecure`。
> 3. HTTP `27123` 在启用 HTTPS 时通常不监听；若 `27124` 不通，先确认 Obsidian 已启动且 Local REST API 插件已启用。

## ⛔ 硬性约束：vault 笔记只能走 API，禁止直接文件操作

**任何对 `<repo-root>/knowledge/` 下笔记文件（`.md`）的读写，必须且只能通过 Obsidian Local REST API（`curl → https://127.0.0.1:27124`）完成。**

🚫 **绝对禁止**用以下方式直接访问 vault 笔记：
- `Read` / `Write` / `Edit` / `Grep` 工具直接读 `<repo-root>/knowledge/**` 下的文件
- 用 `cat` / `sed` / 直接写盘等方式绕过 API 改 vault 内容

**为什么**：直读直写会绕过 Obsidian 的链接索引、Dataview、标签与 frontmatter 缓存，导致双链失效、索引脱节。Local REST API 是 Obsidian 官方写入口，写进去它才认。

✅ **唯一允许直接文件工具修改的，只有本 skill 自身的定义文件**：`SKILL.md`、`playbooks/*`、`references/*`、`api-key.txt`。这些不是 vault 笔记，改它们不影响你的知识库。

**自检口诀**：要动 `<repo-root>/knowledge/` 里的 `.md`？→ 先问「这条 curl 打到 27124 了吗？」没走 API 就停手。

## 子命令

| 子命令 | Playbook | 用途 |
|--------|----------|------|
| `/obsidian-knowledge write [topic]` | [playbooks/create.md](playbooks/create.md) | 新建笔记（Inbox 或领域） |
| `/obsidian-knowledge import <URL\|path>` | [playbooks/create.md](playbooks/create.md) | 外部来源导入（含结构分析 + 拆分） |
| `/obsidian-knowledge organize` | [playbooks/organize.md](playbooks/organize.md) | 批量整理 Inbox |
| `/obsidian-knowledge move <file> <domain>` | [playbooks/organize.md](playbooks/organize.md) | 手动归类单篇到领域 |
| `/obsidian-knowledge dedup` | [playbooks/organize.md](playbooks/organize.md) | 全库去重检测 |
| `/obsidian-knowledge check [--fix]` | [playbooks/audit.md](playbooks/audit.md) | 通过 API 执行静态规范性检查 |
| `/obsidian-knowledge review [--days N]` | [playbooks/review.md](playbooks/review.md) | 周期性深度审查（逐文档 subagent、含 URL 可达性） |
| `/obsidian-knowledge compile <URL\|path>` | [playbooks/compile.md](playbooks/compile.md) | 外部文档 → 结构化笔记（实体提取 + 交叉检测 + SHA256 增量） |
| `/obsidian-knowledge sync` | — | 转交 `gitsync` 处理 submodule 同步 |

> 本 vault 是**个人三领域库**，没有原 agent 知识层的 `01_Compiled/` `02_Schema/` `MOC.md` `tag-registry.md` 等结构。所有路径以下方「架构」为准。

**`check` vs `review`**：
- `/check` = 通过 API 递归读取并执行静态规则扫描（C1-C8）
- `/review` = 深度审查，每文档独立 subagent，含 HTTP 检查 URL 可达性，分钟级
- 日常用 `/check`；定期（每周/每月）用 `/review`

**`import` vs `compile`**：
- `/import` = 快速捕获，轻量结构化，直接落 Inbox/领域
- `/compile` = 深度编译，实体提取 + 关联检测 + SHA256 增量，产出带来源与摘要的结构化笔记

## 前置条件

### API Key 配置

读取顺序：

1. 环境变量 `OBSIDIAN_API_KEY`
2. `<skill-root>/api-key.txt`
3. 都没有 → 提示用户：Obsidian → Settings → Local REST API → 复制 Key；不要读取 vault 内的插件配置文件

### 服务器状态检查

```bash
curl -skf -o /dev/null https://127.0.0.1:27124/ && echo OK || echo DOWN
```

DOWN → 提示用户启动 Obsidian 并启用插件；停止 vault 操作。

### 认证

```bash
KEY="${OBSIDIAN_API_KEY:-$(cat <skill-root>/api-key.txt 2>/dev/null)}"
AUTH="Authorization: Bearer $KEY"
```

## 架构

Vault 采用「顶层只放领域、只增不改」的个人知识库结构（权威规则见 `knowledge/_meta/命名与归档规则.md`）：

```
knowledge/
├── 00-inbox/        # 收件箱：随手记，每周清空归位
├── 10-科研/          # 领域：课题/论文/学术阅读；内含 _MOC.md、各单元文件夹、可选 _archive/
├── 20-教学/          # 领域：courses/（按课程）+ students/（按学生）
├── 30-家庭/          # 领域：孩子的上学/学习/运动/健康
└── _meta/           # 库自身规则/模板/总索引
    ├── HOME.md               # 总索引（根入口）
    ├── 命名与归档规则.md      # 权威规则（四条不变式）
    ├── 插件建议.md
    └── templates/           # 笔记/课程/课题/人物/日志 五套模板
```

- **新领域只增不改**：编号以 10 为步长（`40-xxx` / `50-xxx`…），不改动已有目录。
- **领域内新单元 = 新文件夹**（一门课、一个课题、一个学生、一个孩子）。
- **归档不出领域**：完结内容进本领域 `_archive/`，或仅改 `status: archived`。
- **附件不出领域**：Obsidian 已配置自动存入当前笔记同级 `_attachments/`。

完整 schema 见 [references/vault-schema.md](references/vault-schema.md)。

## Obsidian-native 约定（重要）

Obsidian 的价值来自 **wikilinks × tags × graph** 的网络效应。每次写操作必须遵循：

1. **Wikilinks**：正文用 `[[笔记名]]` 链接相关笔记（含跨领域）。新笔记至少 wikilink 1 篇相关笔记或本域 `_MOC.md` / `_meta/HOME.md`。Rename/move 时扫反向链接并更新。
2. **MOC（手动维护）**：根入口 `_meta/HOME.md`；每个领域根下有 `_MOC.md` 作为该领域地图页，**手动维护、保持简短**（Obsidian graph 负责聚簇，不强制 Dataview）。新增/删除笔记后，在对应 `_MOC.md` 追加/移除一行 `- [[笔记名]]`。
3. **Templates**：新建笔记前，先从 `_meta/templates/` 复制对应模板（笔记/课程/课题/人物/日志）作为骨架；无合适模板再手搓 frontmatter。
4. **Graph 思维**：不要只靠目录层级——让两级标签 + wikilinks 把笔记在 graph view 中自然聚到领域簇。
5. **中文自然命名**：文件名用见名知义的中文（如 `第3章教案.md`、`审稿意见回复.md`），**不**用 kebab-case 或纯英文（日志类例外：`YYYY-MM-DD.md`）。

## 操作前必读

任何写操作前，先获取最新规则与领域地图：

```bash
# 权威规则（四条不变式 + frontmatter/标签/命名规范）
curl -H "$AUTH" https://127.0.0.1:27124/vault/_meta/%E5%91%BD%E5%90%8D%E4%B8%8E%E5%BD%92%E6%A1%A3%E8%A7%84%E5%88%99.md
# 各域地图（手动维护的 _MOC.md）
curl -H "$AUTH" https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/_MOC.md
curl -H "$AUTH" https://127.0.0.1:27124/vault/20-%E6%95%99%E5%AD%A6/_MOC.md
curl -H "$AUTH" https://127.0.0.1:27124/vault/30-%E5%AE%B6%E5%BA%AD/_MOC.md
# 根索引
curl -H "$AUTH" https://127.0.0.1:27124/vault/_meta/HOME.md
```

> 本 vault **没有** `tag-registry.md` / `topics-registry.md` 这类集中登记表。标签与领域的权威定义就是 `_meta/命名与归档规则.md` + 各域 `_MOC.md`。

## Frontmatter 字段规范

所有 .md 笔记必带**最小三字段**（详见 `references/vault-schema.md`）：

| 字段 | 必填 | 取值 | 说明 |
|------|------|------|------|
| `type` | 是 | `note` / `course` / `project` / `person` / `log` | 文档类型 |
| `status` | 是 | `active` / `archived` | 生命周期状态 |
| `created` | 是 | ISO 日期 `2026-07-25` | 创建日期 |
| `tags` | 选填但建议 | YAML 中写 `科研/算子空间` 等（不带 `#`） | 以领域开头，用于跨文件夹检索；正文内联标签才写 `#科研/算子空间` |
| 其余字段 | 选填 | `semester` / `deadline` / `source` 等 | 按需自加 |

外部来源笔记建议在正文开头或 frontmatter 标注 `source`（URL/出处）。

## 检索（API 速查，各 playbook 共用）

> API 细节以当前服务的 `GET /openapi.yaml` 为准，不钉死插件或 Obsidian 版本。
> **简单搜索必须用 POST 的 `query` URL 参数**；不要把查询放进 JSON body。

**① 标签概览（推荐首选：看主题分布 / 最近在做什么）**：
```bash
curl -s -k "$BASE/tags/" -H "$AUTH"
```

**② 简单搜索（POST + URL 编码的 `query` 参数）**：
```bash
curl -s -k -X POST -G "$BASE/search/simple/" \
  -H "$AUTH" --data-urlencode "query=关键词"
```

**③ JsonLogic 结构化搜索（部分版本可用）**：
```bash
curl -s -k -X POST "$BASE/search/" -H "$AUTH" \
  -H "Content-Type: application/json" \
  --data-binary '{"query":{"in":["科研/算子空间",{"var":"tags"}]}}'
```
> 若 ③ 返回空数组，回退到 ①+②。

结果按 score 降序，展示 filename / path / score / 匹配上下文。

## 同步

Git 同步**不在本 skill 实现**，转交：
- `gitsync`：submodule 远端拉取
- `smart-commit`：submodule pointer bump 提交

## API 不可用

当 `27124` 不可达或没有 API key 时，停止 vault 操作并报告阻塞原因。不得降级为文件系统读写。

## 约束

- **中文自然命名**：文件名见名知义的中文/数字，**禁止** kebab-case 与纯英文（日志类 `YYYY-MM-DD.md` 例外）
- **标签两级且以领域开头**：frontmatter 的 `tags` 值写 `科研/...` `教学/...` `家庭/...`（不带 `#`）；正文内联标签写 `#科研/...`；标签不替代文件夹
- **顶层只放领域且只增不改**：顶层只能是 `00-inbox` / `NN-领域` / `_meta`；新领域用 `40-xxx` 等编号，不改动已有目录
- **归档不出领域**：完结内容进本领域 `_archive/` 或 `status: archived`，**禁止**全局归档目录
- **附件不出领域**：附件随笔记存同级 `_attachments/`，**禁止**全局附件目录
- **`_meta/` 受保护**：默认只读。仅以下情况允许写：
  - 新增领域/规则 → 改 `命名与归档规则.md`
  - 用户明确要求
- **`_MOC.md` / `HOME.md` 只追加链接，不删除条目**（除非用户要求清理）
- **Rename/move 必扫反向链接**：search API 找所有 `[[old]]`；逐篇 GET 最新全文、在内存中精确替换、PUT、再 GET 校验。通用 wikilink 替换不使用结构化 PATCH
- **原子 move**：PUT → GET 校验 → DELETE，避免半失败产生重复
- **路径含中文/空格须 URL 编码**：Local REST API 的 vault 路径中的中文与空格需 percent-encode（如 `20-教学` → `20-%E6%95%99%E5%AD%A6`）

## API 端点速查

| 操作 | Method | Path | Auth |
|------|--------|------|------|
| 状态检查 | GET | `/` | 否 |
| 读文件 | GET | `/vault/{path}` | 是 |
| 创建/覆盖 | PUT | `/vault/{path}` | 是 |
| 部分编辑 | PATCH | `/vault/{path}` | 是 |
| 删除 | DELETE | `/vault/{path}` | 是 |
| 列目录 | GET | `/vault/{path}/` | 是 |
| 简单搜索 | POST | `/search/simple/` | 是 |
| 结构化搜索 | POST | `/search/` | 是 |
| 列 tags | GET | `/tags/` | 是 |
| 打开文件 | POST | `/open/{path}` | 是 |

## 扩展指南

新增工作流 = 新增 playbook：

1. 在 `playbooks/` 新建 `<name>.md`，遵循现有 playbook 格式（标题、流程、API 调用示例、约束）
2. 在「子命令」表加一行，指向新 playbook
3. 在 frontmatter `triggers` 加新触发词
4. 不要在本文件加操作细节——一律下沉到 playbook
