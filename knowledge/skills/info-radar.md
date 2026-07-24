# 信息雷达 Skill 使用手册

> 多源技术文章追踪 + AI 评估 + content-pipeline 自动转化

## 快速开始

在 Claude Code 会话中输入以下任一触发词即可启动信息雷达：

| 触发词 | 示例 |
|--------|------|
| `信息雷达` | 「跑一下信息雷达」 |
| `选题扫榜` | 「选题扫榜，看看有什么好文章」 |
| `扫文章` | 「扫文章」 |
| `info-radar` | 「info-radar」 |
| `追踪技术文章` | 「追踪技术文章」 |
| `AI 选题` | 「AI 选题」 |
| `扫博客` | 「扫博客」 |
| `HN 排行` | 「HN 排行」 |

Skill 启动后将自动执行 6 步工作流：读取配置 → 拉取源 → 去重 → 评估 → 报告 → 创建 feature。

## 工作流概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 读取 sources.yaml 配置                                 │
│  ├── 内置源开关、评估权重、关注主题、用户源、转化模式              │
│  └── Gate: 配置文件存在且可解析                                   │
├─────────────────────────────────────────────────────────────────┤
│  Step 2: 拉取内置源（WebFetch）                                  │
│  ├── Anthropic Blog / OpenAI Blog / DeepSeek Blog               │
│  ├── GitHub Trending / Hacker News                              │
│  ├── RSSHub: 36kr / 虎嗅 / 知乎热榜                              │
│  └── Gate: 至少 3 个源成功返回                                    │
├─────────────────────────────────────────────────────────────────┤
│  Step 3: 拉取用户源（可选）                                      │
│  ├── wewe-rss 微信公众号源                                       │
│  ├── 任意 RSS/Atom 源                                            │
│  └── Gate: 失败不影响主流程                                      │
├─────────────────────────────────────────────────────────────────┤
│  Step 4: 三层去重                                                │
│  ├── URL 精确去重（清理 tracking 参数）                           │
│  ├── 主题语义去重（Claude 判定相似度）                             │
│  └── 已有 feature 去重（检查 features/content-pipeline/）         │
├─────────────────────────────────────────────────────────────────┤
│  Step 5: Claude 四维评估                                         │
│  ├── 内容质量 30% / 主题匹配 25% / 热点趋势 20% / 视频适配度 25%  │
│  └── 输出 Markdown 评估报告                                      │
├─────────────────────────────────────────────────────────────────┤
│  Step 6: 转化为 content-pipeline feature                        │
│  ├── confirm 模式：逐篇询问是否创建                               │
│  └── auto 模式：总分 >= 80 自动创建                               │
└─────────────────────────────────────────────────────────────────┘
```

## 内置源

9 个内置源零配置可用，全部默认开启：

| 源 | URL | 类型 | 每次拉取 | 说明 |
|----|-----|------|---------|------|
| Anthropic Blog | `anthropic.com/blog` | 博客列表 | 10 篇 | 降级 URL: `anthropic.com/news`（纯 SPA，当前不可用） |
| OpenAI Blog | `openai.com/blog` | 博客列表 | 10 篇 | 降级: `openai.com/blog/rss.xml`（HTML 被 Cloudflare 拦截） |
| Google Blog | `blog.google/rss/` | RSS | 10 篇 | 降级: `blog.google/technology/ai/` |
| DeepSeek Blog | `api-docs.deepseek.com/updates` | 博客列表 | 10 篇 | — |
| GitHub Trending | `github.com/trending` | HTML 页面 | 25 个 | 可配置语言过滤 |
| Hacker News | Firebase API (JSON) | API | 30 篇 | 最低 score: 100 |
| 36kr 热榜 | `rsshub.app/36kr/hot-list` | RSS | 15 篇 | 降级: `rsshub.rssforever.com` |
| 虎嗅 | `rsshub.app/huxiu/article` | RSS | 15 篇 | 降级: `rsshub.rssforever.com` |
| 知乎热榜 | `rsshub.app/zhihu/hotlist` | RSS | 15 篇 | 降级: `rsshub.rssforever.com` |

**关闭某个源**：编辑 `skills/info-radar/references/sources.yaml`，将对应 `enabled` 改为 `false`。

## 评估维度

每篇文章从 4 个维度打分，总分范围 [0, 100]：

| 维度 | 权重 | 评估内容 | 数据来源 |
|------|------|---------|---------|
| 内容质量 | 30% | 深度、原创性、信息密度、技术含量 | 文章标题 + 摘要 |
| 主题匹配 | 25% | 与关注主题列表的语义匹配 | 文章内容 vs `sources.yaml` topics |
| 热点趋势 | 20% | HN 排名 / GitHub stars / 社交讨论度 | 来源元数据 |
| 视频适配度 | 25% | 叙事性、可视化潜力、话题性、时长预估 | 文章标题 + 摘要 |

**热点趋势默认值**：官方博客无热度指标，此维度默认 60 分。

### 校准规则

评估时自动应用以下规则确保一致性：

1. **官方博客趋势分默认 60** — Anthropic/OpenAI/DeepSeek 发布无外部热度指标
2. **HN 低分上限** — score < 100 的文章，趋势分不超过 50
3. **GitHub Trending 映射** — 前三 85 分，4-10 名 75 分，其余 65 分
4. **API 变更日志上限** — 纯 API 变更日志，视频适配度不超过 40
5. **深度长文基准** — 摘要 > 200 字且含技术细节，内容质量基准 70+
6. **同源评分分散** — 同一来源多篇文章，评分应有明显梯度

### 分数解读

| 总分 | 含义 | 自动处理 |
|------|------|---------|
| >= 80 | 推荐选题 | auto 模式自动创建 feature；confirm 模式列入推荐 |
| 60-79 | 值得关注 | 列入报告但不自动创建 |
| < 60 | 低分文章 | 仅在报告中简略展示 |

## 关注主题

当前默认关注主题（可在 `sources.yaml` 中修改）：

```
- Anthropic / Claude / Agent
- AI / 大模型 / LLM
- 开发工具 / CLI / 编辑器
- 开源项目 / 技术架构
- AI 安全 / 沙箱 / 隔离
- AI 创业 / 商业化
- Rust / 系统编程 / AI 工程化
```

增减主题直接影响「主题匹配」维度的评分。

## 配置文件

所有配置集中在 `skills/info-radar/references/sources.yaml`：

### 内置源开关

```yaml
built_in_sources:
  anthropic_blog:
    enabled: true          # 设为 false 跳过此源
    max_articles: 10       # 每次最多拉取篇数
  hacker_news:
    enabled: true
    min_score: 100         # HN 最低分数过滤
  # ...
```

### 评估参数

```yaml
evaluation:
  weights:
    content_quality: 0.30
    topic_match: 0.25
    trend_relevance: 0.20
    video_fitness: 0.25
  auto_convert_threshold: 80    # 自动创建 feature 的最低分
  recommend_threshold: 60       # 推荐展示的最低分
  default_video_type: mid-video # mid-video | short-video | narration
```

### 转化模式

```yaml
convert_mode: confirm   # confirm = 手动逐篇确认 | auto = 全自动
```

- **confirm**（默认）：评估报告输出后，逐篇询问「是否为这篇创建 mid-video feature？」
- **auto**：总分 >= 80 的文章自动创建 feature，不需要人工确认

### 去重配置

```yaml
dedup:
  check_existing_features: true   # 检查现有 feature 避免重复
  url_ignore_params:              # URL 去重时忽略的 tracking 参数
    - utm_source
    - utm_medium
    - utm_campaign
    - ref
    - source
```

## 用户源：微信公众号 RSS

内置源覆盖英文技术博客和中文科技媒体，但**微信公众号**文章需自建 RSS 服务获取。

### wewe-rss 自建指南

wewe-rss 是一个将微信公众号转为 RSS 的开源项目。

#### 前置要求

- Docker 或 Node.js 18+ 运行环境
- 一个微信读书账号（wewe-rss 通过微信读书接口获取公众号文章）

#### Docker 部署

```bash
docker run -d \
  --name wewe-rss \
  -p 4000:4000 \
  -e MAX_REQUEST_PER_MINUTE=6 \
  -e AUTH_CODE=your_auth_code \
  cooderl/wewe-rss:latest
```

关键环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MAX_REQUEST_PER_MINUTE` | 每分钟最大请求次数 | 6 |
| `AUTH_CODE` | 访问密码（留空则无需密码） | 空 |
| `PORT` | 服务端口 | 4000 |

#### 使用步骤

1. 启动服务后访问 `http://localhost:4000`
2. 登录微信读书账号
3. 搜索并关注目标公众号
4. 获取 RSS 地址：`http://localhost:4000/api/rss/{公众号ID}`

#### 配置到信息雷达

编辑 `skills/info-radar/references/sources.yaml`：

```yaml
user_sources:
  - name: 机器之心
    url: http://localhost:4000/api/rss/mp.weixin.qq.com/机器之心ID
    type: wechat
    enabled: true
    max_articles: 20
  - name: 个人 Substack
    url: https://example.substack.com/feed
    type: rss
    enabled: true
    max_articles: 10
```

**type 字段说明**：

| type | 格式 | 适用场景 |
|------|------|---------|
| `wechat` | RSS 2.0 | wewe-rss 提供的微信公众号源 |
| `rss` | RSS 2.0 | 标准 RSS feed |
| `atom` | Atom | Atom 格式 feed |

#### 常见问题

**Q: wewe-rss 启动后无法登录微信读书？**
A: 检查网络环境，微信读书接口可能需要国内 IP。如从海外访问，需配置代理。

**Q: RSS 地址中的公众号 ID 怎么获取？**
A: 在 wewe-rss Web 界面搜索公众号后，点击对应 RSS 图标即可复制完整 RSS URL。

**Q: wewe-rss 不可用时信息雷达会报错吗？**
A: 不会。用户源拉取失败仅发出警告，不影响内置源的正常运行（Step 3 Gate：失败不影响主流程）。

### 其他 RSS 源

任何标准 RSS/Atom feed 都可作为用户源添加：

```yaml
user_sources:
  - name: Hacker Newsletter
    url: https://hackernewsletter.com/rss
    type: rss
    enabled: true
    max_articles: 20
```

## 评估报告格式

每次扫描输出 Markdown 报告，包含：

```
## 信息雷达报告 — YYYY-MM-DD

### 扫描概览
- 扫描时间、启用源数量、拉取/去重文章数

### 评估结果
- 表格：标题 | 来源 | 质量 | 匹配 | 趋势 | 适配 | 总分

### 推荐选题（总分 >= 80）
- 逐篇展示：来源、原文链接、评估理由、建议选题方向、预估时长

### 主题相似（已去重）
- 同一事件不同报道的归并

### 已有相似选题
- 与 features/content-pipeline/ 现有 feature 主题重叠的文章
```

## 自动创建 Feature 流程

总分 >= `auto_convert_threshold`（默认 80 分）的文章可自动创建 content-pipeline feature：

1. **生成 feature-id**：`{关键词}-mid-video`（如 `claude-code-ai-agents-mid-video`）
2. **创建目录**：`features/content-pipeline/{feature-id}/`
3. **复制模板**：从 `features/_template/content-production/production/` 复制目录结构
4. **生成 spec.md**：基于 `spec-content-pipeline.md` 模板，默认 `tts.action: 0`、`render.stack: remotion-pipelines`
5. **生成 00-podcast-source.md**：填充素材来源、节目定位、钩子、章节要点
6. **更新 INDEX.md**：在表格末尾追加新行

### TTS 路由说明

信息雷达创建的 feature 遵循 content-pipeline 默认路由：

| 项 | 默认值 | 说明 |
|----|--------|------|
| 引擎 | `volc-podcast-tts` | 双人播客中视频 |
| action | `0` | 长文总结生成播客，非逐字对白 |
| 时间轴真源 | `wav_srt` | 以 WAV + SRT 为准 |
| 视频类型 | `mid-video` | 3-15 分钟中视频 |

> 禁止在未填 `tts.override_reason` 的情况下改为 action=3。详见 `knowledge/standards/content-pipeline-tts-routing.md`。

## 常见问题

### Q: 内置源拉取失败怎么办？

每个内置源都有独立的失败处理机制：
- **博客源**（Anthropic/OpenAI/DeepSeek）：自动尝试降级 URL；页面结构变化需更新 SKILL.md 中的 WebFetch prompt
- **GitHub Trending / HN API**：稳定性较高，罕见失败
- **RSSHub 公共实例**：可能限流（429），自动尝试 `rsshub.rssforever.com` 降级

Gate 条件：至少 3 个源成功即可继续。全部失败则报告错误并终止。

### Q: 如何只扫描部分源？

编辑 `sources.yaml`，将不需要的源设为 `enabled: false`：

```yaml
built_in_sources:
  anthropic_blog:
    enabled: true
  openai_blog:
    enabled: false    # 跳过 OpenAI
  google_blog:
    enabled: true
  rsshub_36kr:
    enabled: false    # 跳过 36kr
```

### Q: 如何调整评估权重？

修改 `sources.yaml` 中的 `evaluation.weights`，注意权重总和须为 1.0：

```yaml
evaluation:
  weights:
    content_quality: 0.40    # 加大内容质量权重
    topic_match: 0.25
    trend_relevance: 0.10    # 降低趋势权重
    video_fitness: 0.25
```

### Q: auto 模式会不会创建太多 feature？

auto 模式仅对总分 >= 80 的文章自动创建。根据评估校准规则：
- 官方博客深度长文通常在 75-90 分区间
- HN 热门文章 + 高匹配主题可达 80+
- 低质量文章（API 变更日志等）通常 < 40

如觉得阈值过低，调高 `auto_convert_threshold`：

```yaml
evaluation:
  auto_convert_threshold: 85   # 提高阈值，更严格筛选
```

### Q: 如何添加新的关注主题？

编辑 `sources.yaml` 的 `topics` 列表：

```yaml
topics:
  - Anthropic / Claude / Agent
  - AI / 大模型 / LLM
  - 开发工具 / CLI / 编辑器
  - 开源项目 / 技术架构
  - AI 安全 / 沙箱 / 隔离
  - AI 创业 / 商业化
  - Rust / 系统编程 / AI 工程化
  - Web3 / 区块链              # 新增主题
```

### Q: GitHub Trending 能否只看特定语言？

可以。编辑 `sources.yaml` 启用 `language_filter`：

```yaml
github_trending:
  enabled: true
  language_filter:
    - python
    - typescript
```

### Q: 创建的 feature 和已有选题重复了怎么办？

信息雷达有三层去重机制：
1. **URL 去重**：同一 URL 不会重复拉取
2. **主题去重**：Claude 判定标题+摘要高度相似时保留热度更高的版本
3. **Feature 去重**：检查 `features/content-pipeline/` 下已有选题，URL 匹配则跳过，标题相似则标记

如仍出现重复，可在 Step 6 confirm 模式中手动拒绝创建。

## 文件结构

```
skills/info-radar/
├── SKILL.md                    # Skill 工作流定义（6 步流程 + Gate 条件）
└── references/
    ├── sources.yaml            # 源配置 + 评估权重 + 主题 + 去重
    └── eval-criteria.md        # 评估维度 + 打分标准 + prompt 模板
```

## 相关文档

- `skills/info-radar/SKILL.md` — 完整 6 步工作流定义
- `skills/info-radar/references/eval-criteria.md` — 评估标准与 prompt 模板
- `features/_template/spec-content-pipeline.md` — content-pipeline spec 模板
- `knowledge/standards/content-pipeline-tts-routing.md` — TTS 路由规范
- `knowledge/standards/video-voiceover-script-conventions.md` — 口播稿规范