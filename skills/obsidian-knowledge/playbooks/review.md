> ⛔ 本 playbook 的 vault 读取与写入必须全部走 Obsidian Local REST API。API 或 key 不可用时立即停止；禁止文件系统降级。

# Playbook: review

**子命令**：`/obsidian-knowledge review [--days N] [--dir <vault-path>]`

**定位**：周期性深度审查。默认跳过 7 天内已审查的笔记；审查内容、更新记录、移动和反向链接修复均经 API 完成。

## 前置

1. 读完主 `SKILL.md`。
2. 从 `OBSIDIAN_API_KEY` 或本 skill 的 `api-key.txt` 取 key。
3. `GET https://127.0.0.1:27124/` 确认服务在线。
4. 用一个已知只读端点验证认证；失败则停止。

不得读取 `knowledge/.obsidian/**` 获取 key，也不得用 `Glob`、`Read`、`Grep`、`find`、`rg` 或同类工具扫描 vault。

## Phase 1：API 扫描与筛选

1. 从 `GET /vault/` 开始递归列目录；`--dir` 只改变 API 起始路径。
2. 仅保留 `.md`；排除 `README.md`、`_meta/**`、各领域 `_MOC.md`。
3. 对候选逐篇 `GET /vault/{url-encoded-path}`。
4. 从 `<!-- kb-review -->` 块解析最近审查日期：无记录或距今超过 `N` 天才进入待审查列表。
5. 在执行任何写入前，向用户展示数量和待审查路径。

## Phase 2：逐篇审查

逐篇顺序执行，避免 API 与外部链接检查限流。给每个审查 subagent 的内容必须来自 API 响应，而不是文件路径直读。

检查三类问题：

- 来源完整性：外部导入是否包含来源、作者、发布日期、收录日期。
- 来源可达性：检查来源与正文前 5 个关键公网 URL；内网链接标为人工确认。
- 格式规范性：中文自然文件名、合法 Markdown、正文不少于 20 行、`type/status/created`、frontmatter 中不带 `#` 的领域二级标签、至少一个 wikilink。

只自动修正确定的问题；不得删改事实内容。重命名、失效来源、无法验证的内网链接只提出建议。

修正方式：

1. 基于 API 取得的最新全文生成最小修改。
2. heading、block、frontmatter 等结构化目标可使用 `PATCH`；任意正文或 wikilink 修改必须 GET 最新全文、在内存中精确替换、PUT 全文。
3. 再次 `GET` 校验结果；不要把私人笔记写入临时文件。
4. 在末尾新增或替换唯一的审查块：

```markdown
<!-- kb-review -->
> 📋 审查记录
> - 审查时间: YYYY-MM-DD
> - 审查结果: ✅通过 / ⚠️已修正 / ❌需人工处理
> - 修正简述: 具体问题；无问题则写“无”
<!-- /kb-review -->
```

## Phase 3：汇总

报告扫描数、跳过数、通过数、已修正数、需人工处理数，以及每篇的路径和问题摘要。不要回显 API key 或完整私人笔记内容。

## API 约束

- 中文、空格和 `#` 必须 percent-encode。
- 移动采用 `PUT` 新路径 → `GET` 校验 → `DELETE` 旧路径。
- 移动或重命名前用搜索 API 找反向链接，随后逐篇 GET → 内存精确替换 → PUT → GET 校验。
- API 写入失败时保留原笔记，停止该篇后续操作并报告。
