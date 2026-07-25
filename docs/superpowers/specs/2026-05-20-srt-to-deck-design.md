# srt-to-deck: SRT 驱动的动画级幻灯自动生成

## 元数据

| 字段 | 值 |
|------|------|
| 日期 | 2026-05-20 |
| 状态 | draft |
| 归属 skill | `skills/html-video-from-slides` |
| 影响范围 | cli.js, lib/, assets/, pipeline/, references/ |
| 前置依赖 | 现有 SRT 解析、appear-at 体系、TEMPLATES.md、base.css |

## 1. 背景与问题

现有 `html-video-from-slides` skill 的 `video-pipeline.step.yaml` 中，Step 8（内容板生成）和 Step 9（视觉细化 HTML）均为 reasoning 步骤，需要 Agent 对话式完成。但缺少从 SRT 字幕到 presentation.html 的端到端自动化路径。

当前工作流：

1. 手动/对话式创建 presentation.html
2. 手动/对话式决定翻页时长
3. `srt-map` 指定 SRT 条目范围 → wav-durations.json
4. `appear-at-gen.js` 推算元素出现时序
5. `appear-at-apply.js` 注入 HTML
6. `wav` / `wav-record` 成片

**痛点**：步骤 1-2 是纯手工瓶颈，且 SRT 已包含全部时间信息和文本内容，本可作为源头数据驱动整个流程。

## 2. 目标

新增 `srt-to-deck` 能力，以 skill 形式提供从 SRT 到动画级 presentation.html 的半自动流水线：

- **输入**：`sub.srt` + 可选的 `00-structure.md` / `01-script.md` / `video-input.json`
- **输出**：`presentation.html`（含 `data-appear-at`）+ `wav-durations.json` + 中间产物
- **自动化**：脚本步骤处理纯逻辑（SRT 解析、时长计算、HTML 装配、appear-at 注入），reasoning 步骤由 Claude Code 执行语义分页、内容提炼、配色微调
- **可中断**：每个中间产物均可人工审阅和修改
- **可扩展**：主题库和 SVG 片段库独立维护，增量扩充

## 3. 架构与数据流

```
sub.srt ──┐
           ├─→ Step 1 [脚本]  SRT 解析
00-structure.md ──┘       │
                          ▼
                  srt-parsed.json
                          │
                          ▼
01-script.md ──────→ Step 2 [reasoning] 语义分页
                          │
                          ▼
                  page-splits.json
                          │
                          ▼
                  Step 3 [reasoning] 内容板生成
                          │
                          ▼
                  content-slabs.json
                          │
      themes/_registry.json ──┤
      TEMPLATES.md ──────────┤
      svg-snippets.md ───────┤
                              ▼
                  Step 4 [脚本] HTML 装配
                          │
                          ▼
                  presentation.html (骨架)
                          │
      srt-parsed.json ──────┤
      page-splits.json ─────┤
                              ▼
                  Step 5 [脚本] data-appear-at 注入
                          │
                          ▼
                  presentation.html (完整)
                          │
                          ▼
                  Step 6 [reasoning] 动画与配色微调 (可选)
                          │
                          ▼
                  Step 7 [脚本] 格式校验
```

同时联产 `wav-durations.json`，可无缝衔接 `wav-auto` 或 `wav-record` 成片。

## 4. 中间产物格式

### 4.1 `timing/srt-parsed.json`（Step 1 输出）

```json
{
  "source": "subtitles/sub.srt",
  "totalEntries": 134,
  "totalDurationMs": 331720,
  "entries": [
    { "index": 1, "startMs": 0, "endMs": 3680, "text": "今天咱们要聊的是..." },
    { "index": 2, "startMs": 3680, "endMs": 7820, "text": "可以自动的去进化..." }
  ]
}
```

### 4.2 `timing/page-splits.json`（Step 2 输出）

```json
{
  "source": "timing/srt-parsed.json",
  "structureRef": "content/00-structure.md",
  "pages": [
    {
      "pageId": 0,
      "role": "cover",
      "title": "SkillClaw：Agent 技能自动进化",
      "srtRange": [1, 6],
      "layoutHint": "Cover",
      "rail": "封面"
    },
    {
      "pageId": 1,
      "role": "content",
      "title": "Agent Skill 的三大痛点",
      "srtRange": [7, 30],
      "layoutHint": "Grid2x2",
      "rail": "痛点拆解"
    }
  ]
}
```

字段说明：
- `srtRange`：[from, to] 闭区间，对应 `srt-parsed.json` 的 entry index
- `layoutHint`：推荐模板名，取值范围见 TEMPLATES.md（Cover / Split / Grid2x2 / SlimHeader / TwoCards / Takeaways）
- `role`：`cover` | `content` | `closing`，影响模板选择策略
- `rail`：底栏章节标签

### 4.3 `timing/content-slabs.json`（Step 3 输出）

```json
{
  "theme": "tech-evolve",
  "pages": [
    {
      "pageId": 0,
      "role": "cover",
      "layout": "Cover",
      "title": "SkillClaw：Agent 技能自动进化",
      "subtitle": "去重 · 合并 · 跨端共享",
      "hosts": ["阿哲 · 技术", "小夏 · 观察"],
      "pills": ["技能进化", "开源框架", "群体智能"],
      "wa": "SkillClaw Agent 技能库 自动进化 去重 共享",
      "svgHint": "进化图腾（齿轮/双螺旋）",
      "accentOverride": null
    },
    {
      "pageId": 1,
      "role": "content",
      "layout": "Grid2x2",
      "chapter": "痛点拆解",
      "badge": "问题",
      "heading": "技能库越用越乱？",
      "svgHint": "三叉痛点图",
      "cards": [
        {
          "emoji": "📦",
          "title": "技能膨胀",
          "body": "重复、过期、半成品堆积，无反馈机制",
          "appearKeywords": ["膨胀", "重复"],
          "appearEffect": "slide-up"
        }
      ],
      "wa": "技能膨胀 缺乏消化 经验孤岛 三大问题"
    }
  ]
}
```

字段说明：
- `theme`：主题 ID，引用 `themes/_registry.json`
- `wa`：Whisper 锚文字，用于 `wav-auto` 对齐
- `svgHint`：SVG 图形意图描述，供 Step 4 装配时匹配 svg-snippets.md 或由 Step 6 优化
- `appearEffect`：入场动画效果，取值范围见 5.2 节
- `accentOverride`：可覆盖主题默认配色（用于特殊页面）

## 5. 主题与动画

### 5.1 主题库

```
assets/themes/
├── _registry.json          # 主题注册表
├── tech-evolve.css         # 科技进化风（默认）
├── risk-narrative.css      # 风险叙事风
├── animal-deep.css         # 深林绿黑风
└── ...                     # 后续动态扩充
```

`_registry.json` 结构：

```json
[
  {
    "id": "tech-evolve",
    "name": "科技进化",
    "cssFile": "themes/tech-evolve.css",
    "accent": ["#22d3ee", "#4ade80", "#a78bfa"],
    "keywords": ["技术", "AI", "框架", "开源", "进化", "架构"],
    "svgStyle": "geometric"
  },
  {
    "id": "risk-narrative",
    "name": "风险叙事",
    "cssFile": "themes/risk-narrative.css",
    "accent": ["#ef4444", "#f97316", "#fbbf24"],
    "keywords": ["安全", "风险", "事故", "防护"],
    "svgStyle": "angular"
  }
]
```

**主题选择策略**：
1. `video-input.json` 中 `theme` 字段强制指定 → 优先
2. content-slabs.json 关键词匹配 `_registry.json` 的 `keywords` → 语义推荐
3. 兜底：`tech-evolve`

### 5.2 动画分层

**第 1 层：增强 data-appear-at（必须，所有页面生效）**

现有 timed-appears 运行时通过 `is-appeared` class 切换元素可见性。扩展 `data-appear-effect` 属性控制入场动画：

```css
/* assets/transitions.css 扩展 */
[data-appear-at] {
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.55s cubic-bezier(0.16, 1, 0.3, 1),
              transform 0.55s cubic-bezier(0.16, 1, 0.3, 1);
}
[data-appear-at].is-appeared {
  opacity: 1;
  transform: translateY(0);
}
[data-appear-at][data-appear-effect="slide-left"] {
  transform: translateX(-40px);
}
[data-appear-at][data-appear-effect="slide-left"].is-appeared {
  transform: translateX(0);
}
[data-appear-at][data-appear-effect="scale-in"] {
  transform: scale(0.88);
}
[data-appear-at][data-appear-effect="scale-in"].is-appeared {
  transform: scale(1);
}
[data-appear-at][data-appear-effect="highlight"] {
  transition: background 0.4s, box-shadow 0.4s;
}
[data-appear-at][data-appear-effect="highlight"].is-appeared {
  box-shadow: 0 0 0 2px var(--c-accent-a);
}
```

效果取值：`slide-up`（默认）| `slide-left` | `scale-in` | `highlight` | `none`

**第 2 层：GSAP 集成（可选，用于高级动画）**

- 通过 CDN 引入 GSAP（`https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js`，~25KB gzip）
- 由 content-slabs.json 的 `pageTransition` 字段控制翻页过渡
- 用于：SVG 路径描边动画、数字滚动、翻页 3D 效果
- 录屏模式（`wav-record`）天然支持；截图模式（`wav`）降级为 `__showAllAppeared()` 兜底
- 不引入 reveal.js，因其接管导航生命周期与现有 `go()` + `#P` 体系冲突

## 6. Step 详细设计

### Step 1：SRT 解析（脚本）

**命令**：`node lib/srt_parse.js --project <dir>`

**输入**：`subtitles/sub.srt`

**处理**：
1. 复用 `srt_postprocess.js` 的 `parseSrt()` 解析 SRT
2. 提取每条的时间戳（startMs, endMs）和文本
3. 计算总时长

**输出**：`timing/srt-parsed.json`

### Step 2：语义分页（reasoning）

**输入**：`timing/srt-parsed.json` + `content/00-structure.md`（可选）+ `content/01-script.md`（可选）

**Agent 行为**：
1. 如果有 `00-structure.md`，以其章节结构为分页骨架
2. 如果没有，从 SRT 条目的语义断点（话题转换、对话方切换、"接下来"/"那我们"等过渡语）自动识别分页
3. 为每页分配 SRT 条目范围，推荐布局模板
4. 封面页（role=cover）通常覆盖 SRT 前 2-6 条（开场白）
5. 收尾页（role=closing）覆盖 SRT 最后 2-5 条

**输出**：`timing/page-splits.json`

### Step 3：内容板生成（reasoning）

**输入**：`timing/page-splits.json` + `timing/srt-parsed.json`

**Agent 行为**：
1. 读取每页的 SRT 条目原文
2. 将口语对白浓缩为幻灯文案（标题、要点、pill 标签）
3. 为每页选择布局模板（Cover / Split / Grid2x2 / SlimHeader / TwoCards / Takeaways）
4. 推荐 SVG 图形意图（`svgHint`）
5. 从 `_registry.json` 语义推荐主题
6. 为可出现元素标记 `appearKeywords`（对应 SRT 文本中的关键词）

**输出**：`timing/content-slabs.json`

### Step 4：HTML 装配（脚本）

**命令**：`node lib/deck_assemble.js --project <dir> [--theme <id>]`

**输入**：`timing/content-slabs.json` + `assets/` + `references/TEMPLATES.md`

**处理**：
1. 加载主题 CSS（`_registry.json` → 指定主题的 `.css` 文件）
2. 按 content-slabs 逐页装配 HTML：
   - Cover → 封面模板（进化条 + Hero + Pill 行）
   - Grid2x2 → 四格卡片 + SVG 图形区
   - Split → 左文右图布局
   - 等等
3. 从 `svg-snippets.md` 匹配 SVG 片段（基于 `svgHint` 关键词），未匹配则生成占位 SVG
4. 拼接 `base.css` + 主题 CSS + `transitions.css` + GSAP（如启用）
5. 注入 `go()` 导航函数 + `#prog` 进度条 + `#deck-rail` 底栏
6. 为每页写入 `data-rail` 属性
7. 计算并输出 `timing/wav-durations.json`（从 page-splits 的 srtRange 直接计算）

**输出**：`slides/presentation.html` + `timing/wav-durations.json`

### Step 5：data-appear-at 注入（脚本）

**命令**：`node lib/appear_at_inject.js --project <dir>`

**输入**：`timing/page-splits.json` + `timing/content-slabs.json` + `timing/srt-parsed.json` + `slides/presentation.html`

**处理**：
1. 遍历每页的 SRT 条目，计算页内时间轴（以页内第一条 SRT 的 startMs 为 t=0）
2. 对 HTML 中的可出现元素（卡片、badge、pill 等），根据 content-slabs 中的 `appearKeywords` 匹配 SRT 文本
3. 匹配到的 SRT 条目的 startMs（减去页起始时间）→ `data-appear-at` 值
4. 未匹配的元素按均匀分布填充
5. 写入 `data-appear-effect` 属性（来自 content-slabs）
6. 添加 `data-timed-appears` 到 `#P` 容器
7. 注入 timed-appears 运行时 JS

**输出**：`timing/appear-at-draft.json`（审阅用）+ 更新 `slides/presentation.html`

### Step 6：动画与配色微调（reasoning，可选）

**输入**：`slides/presentation.html`

**Agent 行为**：
1. 审阅 HTML 整体视觉效果
2. 调整 SVG 图形细节、配色微调
3. 优化翻页过渡效果
4. 确认 GSAP 动画不与 timed-appears 冲突

**输出**：更新 `slides/presentation.html`

### Step 7：格式校验（脚本）

**命令**：`node lib/deck_validate.js --project <dir>`

**处理**：
1. HTML 结构验证：每页有 `.s.slide`、有 `data-rail`、有 `.wa`
2. data-appear-at 值合理性检查（非负、页内递增、不超页时长）
3. 主题 CSS 引用检查
4. 可选：调用现有 `timing-check` 做翻页边界语义校验
5. 输出校验报告

## 7. 文件变更清单

| 路径 | 操作 | 说明 |
|------|------|------|
| `skills/html-video-from-slides/cli.js` | 修改 | 新增 `srt-to-deck` 命令路由 |
| `skills/html-video-from-slides/lib/srt_parse.js` | 新增 | SRT 解析脚本 |
| `skills/html-video-from-slides/lib/deck_assemble.js` | 新增 | HTML 装配脚本 |
| `skills/html-video-from-slides/lib/deck_themes.js` | 新增 | 主题注册与加载 |
| `skills/html-video-from-slides/lib/appear_at_inject.js` | 新增 | appear-at 从 page-splits 计算+注入 |
| `skills/html-video-from-slides/lib/deck_validate.js` | 新增 | 格式校验脚本 |
| `skills/html-video-from-slides/pipeline/srt-to-deck.step.yaml` | 新增 | 7 步编排定义 |
| `skills/html-video-from-slides/assets/themes/_registry.json` | 新增 | 主题注册表 |
| `skills/html-video-from-slides/assets/themes/tech-evolve.css` | 新增 | 科技进化主题 |
| `skills/html-video-from-slides/assets/themes/risk-narrative.css` | 新增 | 风险叙事主题（从 ai-agent-security 项目提取） |
| `skills/html-video-from-slides/assets/transitions.css` | 修改 | 新增 data-appear-effect 动画变体 |
| `skills/html-video-from-slides/SKILL.md` | 修改 | 文档更新 |

## 8. 与现有模块的衔接

| 现有模块 | 衔接方式 |
|----------|----------|
| `srt_postprocess.js` | Step 1 复用 `parseSrt()` |
| `srt_map.js` | 不再需要手动 `srt-map --boundaries`，page-splits 自动生成 wav-durations |
| `appear-at-gen.js` | Step 5 替代其功能，但基于 page-splits 而非 wav-durations |
| `appear-at-apply.js` | Step 5 复用其 HTML 注入逻辑（data-appear-at 写入 + 运行时注入） |
| `wav_auto.js` | srt-to-deck 输出的 wav-durations.json 可直接被 wav-auto 消费 |
| `slide_deck.js` | Step 7 格式校验可复用 `countSlides()` |
| `TEMPLATES.md` | Step 4 装配时引用模板定义 |
| `svg-snippets.md` | Step 4 装配时匹配 SVG 片段 |

## 9. 不做的事

- **不引入 reveal.js**：与现有导航体系冲突，改造成本过高
- **不做全自动 SVG 生成**：`svgHint` 供 Step 6 reasoning 优化使用，脚本步骤仅做关键词匹配 + 占位
- **不做 TTS 管线改动**：srt-to-deck 只管生成 HTML，不涉及音频
- **不做移动端适配**：1920x1080 画布为主，mobile-layout.css 不变