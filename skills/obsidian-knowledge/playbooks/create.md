> ⛔ 本 playbook 所有 vault 操作必须走 Obsidian Local REST API（`curl → https://127.0.0.1:27124`）。禁止用 Read/Write/Edit/Grep 直接访问 `knowledge/` 笔记文件——详见主 `SKILL.md`「⛔ 硬性约束」。

# Playbook: create

**子命令**：`/obsidian-knowledge write [topic]` · `/obsidian-knowledge import <URL|path>`

**前置**：读完主 `SKILL.md`，完成 API Key + 规则加载（读 `_meta/命名与归档规则.md` 与各域 `_MOC.md`）。

---

## `/write [topic]` — 新建笔记

### 决策：Inbox vs 领域

| 条件 | 目标路径 | status |
|------|----------|--------|
| 用户未指定领域 / 话题模糊 | `00-inbox/<中文名>.md` | active |
| 用户指定领域（10-科研/20-教学/30-家庭） | `<领域>/<单元>/<中文名>.md` 或 `<领域>/<中文名>.md` | active |
| 用户提议新领域（如 40-行政） | 确认后建 `40-行政/`，遵循「只增不改」 | active |

> 文件名：**中文自然命名**，见名知义（如 `第3章教案.md`）。**禁止** kebab-case / 纯英文（日志类 `YYYY-MM-DD.md` 例外）。
> 路径含中文/空格须 URL 编码（如 `20-教学` → `20-%E6%95%99%E5%AD%A6`）。

### Inbox 快速捕获

```bash
DATE=$(date +%F)
curl -X PUT "https://127.0.0.1:27124/vault/00-inbox/<中文名>.md" \
  -H "$AUTH" -H "Content-Type: text/markdown" \
  --data-binary @- <<EOF
---
type: note
status: active
created: $DATE
tags: [科研/随手]
---

# 标题

内容。相关：[[某篇笔记]]
EOF
```

**Inbox frontmatter 最低要求**：`type`、`status`、`created`。`tags` / `source` 选填。

### 领域结构化笔记

1. 先从 `_meta/templates/` 复制对应模板（笔记/课程/课题/人物/日志）作为骨架：
```bash
curl -H "$AUTH" "https://127.0.0.1:27124/vault/_meta/templates/%E7%AC%94%E8%AE%B0%E6%A8%A1%E6%9D%BF.md"
```
2. 填充内容后 PUT 到目标领域：
```bash
DATE=$(date +%F)
curl -X PUT "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/<单元>/<中文名>.md" \
  -H "$AUTH" -H "Content-Type: text/markdown" \
  --data-binary @- <<EOF
---
type: note
status: active
created: $DATE
tags: [科研/算子空间]
---

# 标题

内容。相关：[[某篇笔记]] 或 [[10-科研/_MOC|科研地图]]
EOF
```

**领域笔记 frontmatter 必填**：`type`、`status`、`created`。外部来源建议标 `source`（URL/出处）。

### 写后自检清单

- [ ] frontmatter 三字段齐备（type/status/created）
- [ ] 文件名中文自然命名（非 kebab-case）
- [ ] 已 wikilink 至少 1 篇相关笔记或本域 `_MOC.md` / `_meta/HOME.md`
- [ ] frontmatter `tags` 两级且以领域开头（如 `科研/...`，不带 `#`；正文内联标签才带 `#`）
- [ ] 与现有笔记无重复（跑 `/dedup`）
- [ ] 更新目标领域 `_MOC.md`（手动追加 `- [[新笔记]]`）

---

## `/import <URL|path>` — 外部来源导入

### 流程

1. **获取内容**：URL → WebFetch；vault 外本地文件 → Read；vault 内路径 → Local REST API GET；剪贴板 → 用户粘贴
2. **结构分析**（强制输出，不可跳过）
3. **拆分决策**：多章节 → 询问 [A] 全部拆分 / [S] 选择部分 / [M] 单文档
4. **逐章创建**：每章独立走 `/write` 流程，各自 wikilink 相关笔记
5. **写后自检**：每篇都过 `/write` 的自检清单

### 结构分析（强制输出）

```
📄 文档结构分析

| 章节 | 独立? | 依据 | 推断领域 | 置信度 |
|-----|------|------|----------|--------|
| 章节A | ✅ | 完整流程 | 10-科研 | 90% |
| 章节B | ❌ | 辅助信息 | - | - |

结论：N 个独立章节，建议拆分/不拆分。
```

**判定维度**：
- 章节是否自成一体（不依赖上下文即可理解）
- 是否有独立标题（H1/H2）
- 主题是否可映射到某领域（科研/教学/家庭）及其子主题
- 长度是否 ≥ 20 行（太短则倾向合并）

### 拆分策略

| 选项 | 行为 |
|------|------|
| [A] 全部拆分 | 每章独立成 note，各自走 /write |
| [S] 选择部分 | 用户勾选要拆的章节，其余合并为 1 篇 |
| [M] 单文档 | 整体作为 1 篇，领域按主章节判定 |

### 来源归属

导入的外部内容**必须**在 frontmatter 或正文开头标注：

```markdown
> 来源：[Article Title](https://example.com/article)
> 作者：Author Name
> 发布日期：YYYY-MM-DD
> 收录日期：YYYY-MM-DD
```

外部来源笔记建议填 `source` 字段（URL）。

### 去重预检

导入前先 `POST /search/simple/` 查主标题关键词。发现高相似 → 询问用户：
- [U] 更新现有笔记（合并新信息）
- [N] 忽略本次导入
- [C] 强制新建（需说明理由）

---

## 共用 API 模式

### _MOC PATCH 安全流程

```bash
# Step1: 读 _MOC，确认目标 heading 存在（如 ## 索引）
MOC=$(curl -H "$AUTH" "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/_MOC.md")
if ! echo "$MOC" | grep -q "^## 索引"; then
  # heading 不存在 → 整体 PUT 重写（在末尾追加新 section）
  # ... 追加 "## 索引\n- [[new-note]]" 后 PUT 回
fi
# Step2: heading 存在，走 PATCH append
curl -X PATCH "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/_MOC.md" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"targetType":"heading","target":["索引"],"operation":"append","content":"\n- [[新笔记]]"}'
```

### 反向链接扫描

新建/重命名笔记后，扫所有 `[[旧名]]` 并更新：

```bash
curl -s -k -X POST -G "https://127.0.0.1:27124/search/simple/" \
  -H "$AUTH" --data-urlencode "query=[[旧名]]"
```

对每个匹配路径：经 API `GET` 最新全文，在进程内存中确认并精确替换 `[[旧名]]`，以全文 `PUT` 回原路径，再次 `GET` 比较确认。不要把私人笔记写入临时文件，也不要用结构化 PATCH 做任意字符串替换。

---

## 约束

- 文件名中文自然命名，**禁止** kebab-case / 纯英文
- frontmatter `tags` 两级且以领域开头（如 `科研/...`，不带 `#`；正文内联标签才带 `#`）
- 新建笔记前先复制 `_meta/templates/` 对应模板
- 笔记至少 wikilink 1 篇相关笔记或 `_MOC.md` / `HOME.md`
- 路径含中文/空格须 URL 编码
- 归档不出领域：完结内容进本领域 `_archive/` 或 `status: archived`
