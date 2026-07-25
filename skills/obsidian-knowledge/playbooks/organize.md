> ⛔ 本 playbook 所有 vault 操作必须走 Obsidian Local REST API（`curl → https://127.0.0.1:27124`）。禁止用 Read/Write/Edit/Grep 直接访问 `knowledge/` 笔记文件——详见主 `SKILL.md`「⛔ 硬性约束」。

# Playbook: organize

**子命令**：`/obsidian-knowledge organize` · `/obsidian-knowledge move <file> <domain>` · `/obsidian-knowledge dedup`

**前置**：读完主 `SKILL.md`，完成 API Key + 规则加载。

---

## `/organize` — 批量整理 Inbox

### 流程

1. `GET /vault/00-inbox/` 列文件
2. 逐一 `GET /vault/00-inbox/<file>` 读内容
3. 对照领域清单（10-科研/20-教学/30-家庭）判断归属
4. **原子 move**：PUT 新位置 → GET 校验 → DELETE 原位置
5. 更新目标领域 `_MOC.md`（PATCH append；heading 缺失则 PUT 重写）
6. 无法归类 → 暂留 Inbox，或提议新领域（`40-xxx`，需用户确认）
7. **整理完跑一次去重**（精确 title + 模糊兜底）

### 归类判定

```
对每篇 Inbox 笔记：
  1. 读 type/status/created + 正文关键词
  2. 与三大领域（科研/教学/家庭）做语义匹配
  3. 置信度高（≥80%）→ 直接 move 到对应领域/单元
  4. 置信度低或跨领域 → 询问用户
  5. 完全无法归类 → 暂留 Inbox
```

### 输出示例

```
📋 Inbox 整理结果

待处理：12 篇
已归类：9 篇
  - 3 篇 → 10-科研
  - 2 篇 → 20-教学
  - 4 篇 → 30-家庭
待确认：2 篇（跨领域，需用户决策）
暂留：1 篇（无法归类）
```

---

## `/move <file> <domain>` — 手动归类

### 流程

1. `GET` 源文件确认内容
2. 更新 frontmatter：
   - 补全 `type` / `status` / `created`
   - `tags` 加入目标领域前缀（如 `#科研/...`）
3. **原子 move**：
   ```bash
   # Step1: PUT 新位置（领域/单元/文件名）
   curl -X PUT "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/<单元>/<中文名>.md" \
     -H "$AUTH" -H "Content-Type: text/markdown" \
     --data-binary @updated-content.md
   # Step2: GET 校验新位置
   curl -H "$AUTH" "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/<单元>/<中文名>.md" | diff - updated-content.md
   # Step3: DELETE 原位置（仅当 Step2 一致）
   curl -X DELETE "https://127.0.0.1:27124/vault/00-inbox/<中文名>.md" -H "$AUTH"
   ```
4. 更新源和目标领域 `_MOC.md`
5. **扫反向链接**：`POST /search/simple/` 查 `[[旧路径]]`，PATCH 所有匹配改为新路径

### 反向链接更新

```bash
# 找所有引用旧路径的笔记
curl -X POST "https://127.0.0.1:27124/search/simple/" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"query": "[[00-inbox/旧名]]"}'

# 对每个匹配文件 PATCH 替换 wikilink
for f in $matching_files; do
  curl -X PATCH "https://127.0.0.1:27124/vault/$f" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"operation":"replace","target":"[[00-inbox/旧名]]","content":"[[10-科研/单元/新名]]"}'
done
```

---

## `/dedup` — 全库去重检测

### 流程

1. `GET /vault/` 列所有顶层目录（排除 `_meta`）
2. 对每个领域目录递归列 `.md` 文件
3. 对每篇笔记：
   - **精确 title 匹配**：`POST /search/simple/` 查文件名/标题关键词（本 vault 以中文名为主）
   - **模糊兜底**：`POST /search/simple/` 查主标题关键词
4. 发现重复 → 列出路径 + 摘要，让用户决定

### 输出示例

```
🔍 去重检测结果

扫描笔记：142 篇
疑似重复：3 组

[1] "算子空间局部性质"
    - 10-科研/算子空间理论/算子空间局部性质.md (2026-07-20)
    - 10-科研/算子空间理论/局部性质笔记.md (2026-07-22)
    → 建议：合并到较新的一篇，删除另一篇

[2] "高等代数教案"
    - 20-教学/2026秋-高等代数/第3章教案.md
    - 20-教学/2026秋-高等代数/教案-第3章.md
    → 建议：保留其一（命名统一）

[3] ...
```

### 用户决策

对每组重复：
- [K] 保留指定篇，删除其他
- [M] 合并内容到一篇，删除其他
- [S] 跳过（保留所有）

---

## 共用 API 模式

### 原子 move（PUT → GET → DELETE）

**关键**：DELETE 前必须 GET 校验新位置内容一致，避免半失败产生重复。

```bash
# Step1: PUT 新位置
curl -X PUT "https://127.0.0.1:27124/vault/<new-path>" \
  -H "$AUTH" -H "Content-Type: text/markdown" \
  --data-binary @content.md

# Step2: GET 校验
curl -s -H "$AUTH" "https://127.0.0.1:27124/vault/<new-path>" > /tmp/new.md
diff /tmp/new.md content.md || { echo "校验失败，跳过 DELETE"; exit 1; }

# Step3: DELETE 原位置
curl -X DELETE "https://127.0.0.1:27124/vault/<old-path>" -H "$AUTH"
```

### _MOC PATCH 安全流程

```bash
MOC=$(curl -H "$AUTH" "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/_MOC.md")
if ! echo "$MOC" | grep -q "^## 索引"; then
  # heading 不存在 → 整体 PUT 重写
fi
curl -X PATCH "https://127.0.0.1:27124/vault/10-%E7%A7%91%E7%A0%94/_MOC.md" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"targetType":"heading","target":["索引"],"operation":"append","content":"\n- [[新笔记]]"}'
```

---

## 约束

- 原子 move：PUT → GET 校验 → DELETE
- Rename/move 必扫反向链接并更新
- 整理完必跑去重
- 标签两级且以领域开头
- 归档不出领域：完结内容进本领域 `_archive/` 或 `status: archived`
- `_MOC.md` 只追加，不删除条目
