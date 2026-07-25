# Deck as Code 框架设计 Spec

| 字段 | 值 |
|------|------|
| 日期 | 2026-05-22 |
| 状态 | draft |
| 归属 skill | `skills/remotion-deck` (扩展为模板化引擎) |
| 影响范围 | 新增 markdown-compiler 模块, 改造 themes/ 目录结构, 修改 cli.cjs/remotion_bridge.cjs/render.cjs/data_loader.ts |
| 前置依赖 | 现有 remotion-deck 帧级渲染管线，srt-to-deck content-slabs 数据格式 |

---

## 1. 目标与范围

### 1.1 解决的问题

| 问题 | 根因 | 本方案如何解决 |
|------|------|---------------|
| **视觉同质化** | 布局分配硬编码，主题只换颜色，图表种类有限 | Markdown 声明式布局 + 自动排版引擎的多多样性约束 + 主题包五维差异 + 图表精确 ID 映射 |
| **数据覆盖** | `public/remotion-data.json` 被第二次生成覆盖 | 每个项目一个 `.md` 文件，产出物全写入项目目录，天然隔离 |
| **布局分配固定** | content-slabs.json 无多样性逻辑 | `layout-policy: diverse` 自动排版 + 内容结构推断 |
| **图表匹配粗糙** | svgHint 正则模糊匹配仅 9 种 | `chart:` 精确 ID + 语义类型映射 + 可视化 DSL |

### 1.2 不解决的问题

| 不做的事 | 原因 |
|----------|------|
| 不做 WYSIWYG 编辑器 | 声明式 Markdown 优先，IDE 原生支持 |
| 不改变 Remotion 渲染管线 | Composition 入口不变，只改变数据供给方式 |
| 不做实时协作 | 单用户 Markdown 文件，Git 管版本 |
| Phase 1 不做 Mermaid 集成 | Phase 1 用精确 ID 映射，Phase 2 再加 Mermaid 子集 |
| 不做 CSS-in-JS 主题运行时 | 主题 Token 编译时固化 |

---

## 2. 核心概念

### 2.1 Markdown DSL

借鉴 Slidev：Markdown 文件 = YAML frontmatter（全局配置）+ 多个用 `---` 分隔的幻灯片块，每块可有自己的 frontmatter（页面级配置）。

```markdown
---
theme: presentation-c
layout-policy: diverse
chart-strategy: semantic
fps: 30
resolution: 1920x1080
---

# AI 会做梦？
<!-- role: cover -->

---

layout: TwoCards
chart: memory-compare
## 事实记忆 vs 行动记忆

:::card{emoji="📖" accent="a"}
### 事实记忆
记住「发生了什么」
:::

:::card{emoji="🎯" accent="b"}
### 行动记忆
学会「下次该怎么做」
:::
```

与 Slidev 的关键差异：
- Slidev 面向现场演讲（键盘翻页），Deck as Code 面向视频渲染（时序驱动）
- Slidev 用 Vue 组件，Deck as Code 输出为 content-slabs.json + remotion-data.json
- Slidev 不关心音频同步，Deck as Code 必须与 wav-durations.json 对齐

### 2.2 主题包

一个主题包 = 一个目录，包含：

```
themes/presentation-c/
├── theme.yaml          # Token 定义（色彩、字号、间距...）
├── styles.css          # HTML 路径的 CSS 变量覆盖
├── tokens.ts           # Remotion 路径的 ThemeTokens（编译时生成）
├── backgrounds/        # 背景策略组件
│   ├── mesh-gradient.tsx
│   └── orbs.tsx
├── animations/         # 动画预设
│   └── default.yaml    # Appear 效果预设
└── layouts/            # 主题专属布局变体（可选覆盖）
    └── cover.tsx
```

### 2.3 自动排版引擎

当页面 frontmatter 未指定 `layout` 时，引擎根据内容结构自动推断：

1. 扫描页面 Markdown AST，统计结构特征
2. 将特征向量输入规则引擎
3. 全局 `layout-policy` 约束介入
4. 输出确定的 layout 值

### 2.4 图表即代码

两层机制：
- **语义类型映射**：frontmatter 的 `chart: memory-compare` 直接映射到图表组件（精确匹配，不再用正则模糊搜索）
- **可视化 DSL**（Phase 2）：支持 Mermaid 语法的子集，在 Markdown 中声明图表数据

---

## 3. Markdown DSL 设计

### 3.1 全局 Frontmatter Schema

```yaml
# === 必填 ===
title: string              # 视频标题

# === 主题与样式 ===
theme: string              # 主题包 ID（默认 tech-evolve）
layout-policy: enum        # diverse | balanced | fixed（默认 diverse）
chart-strategy: enum       # semantic | explicit | auto（默认 semantic）

# === 渲染参数 ===
fps: number                # 帧率（默认 30）
resolution: string         # "1920x1080" | "1080x1920" | "1920x1920"

# === 音频同步 ===
audio: string|null         # WAV 文件路径
srt: string|null           # SRT 文件路径

# === 高级 ===
theme-overrides: object|null  # 主题 Token 逐字段覆盖
```

**layout-policy 取值**：

| 值 | 行为 |
|----|------|
| `diverse` | 强制多样性：最多连续 2 页同布局，整份 deck >= 3 种不同布局 |
| `balanced` | 倾向多样性但不强制；同一布局最多出现 40% 的页面 |
| `fixed` | 完全由页面 frontmatter 决定，不自动调整 |

**chart-strategy 取值**：

| 值 | 行为 |
|----|------|
| `semantic` | 使用 `chart:` 字段精确匹配；匹配不到时用内容结构推断 |
| `explicit` | 仅使用 `chart:` 精确匹配；不声明则无图表 |
| `auto` | 完全由引擎根据内容语义推断图表类型 |

### 3.2 页面级 Frontmatter Schema

```yaml
layout: string             # Cover | Grid2x2 | Split | SlimHeader | TwoCards | Takeaways
role: enum                 # cover | content | closing
chart: string|null         # 图表组件 ID（精确匹配 DIAGRAM_MAP key）
badge: string|null         # 角标文字
chapter: string|null       # 章节标签
accent: string|null        # 强调色覆盖：a | b | c | sk | rd | gn | purple
transition: string|null    # 翻页过渡效果（Phase 2）
duration-override: number|null  # 强制覆盖该页时长（秒）
```

### 3.3 内容语法

#### 容器指令

```markdown
:::cards
卡片内容...
:::

:::left
左侧内容（Split 布局专用）
:::

:::right
右侧内容（Split 布局专用）
:::

:::items
列表项内容（SlimHeader 布局）
:::

:::takeaways
要点列表（Takeaways 布局）
:::
```

#### 卡片定义

```markdown
:::card{emoji="📦" accent="a" effect="slide-up"}
### 技能膨胀
重复、过期堆积，无反馈
:::
```

卡片属性：`emoji`, `accent` (a/b/c/sk/rd/gn/purple), `effect` (slide-up/slide-left/slide-right/scale-in/fade)

#### 条目定义（SlimHeader 用）

```markdown
:::item{icon="🔀" effect="slide-up"}
### Client Proxy
代理所有请求，记录输入/工具调用/反馈/结果
:::
```

#### 要点定义（Takeaways 用）

```markdown
:::takeaway{icon="🧠" effect="slide-up"}
模型 → 推理能力
:::
```

#### 图表声明

```markdown
:::chart{id="memory-compare"}
:::
```

#### Pills 和 Hosts

```markdown
::pills
技能进化 :: 开源框架 :: 群体智能
::

::hosts
阿哲 · 技术 :: 小夏 · 观察
::
```

#### 锚文字

```markdown
::wa
SkillClaw Agent 技能库 自动进化 去重 共享
::
```

### 3.4 完整示例

```markdown
---
theme: presentation-c
layout-policy: diverse
chart-strategy: semantic
title: "SkillClaw：Agent 技能自动进化"
audio: ../media/voiceover.wav
srt: ../subtitles/sub.srt
---

# SkillClaw：Agent 技能自动进化

::pills
技能进化 :: 开源框架 :: 群体智能
::

::hosts
阿哲 · 技术 :: 小夏 · 观察
::

::wa
SkillClaw Agent 技能库 自动进化 去重 共享
::

---

layout: Grid2x2
badge: 问题
chapter: 痛点拆解

## 技能库越用越乱？

:::cards

:::card{emoji="📦" accent="a"}
### 技能膨胀
重复、过期堆积，无反馈
:::

:::card{emoji="🔄" accent="b"}
### 缺乏消化
无去重优化，调用混乱
:::

:::card{emoji="🏝️" accent="c"}
### 经验孤岛
多端无法共享，重复造轮子
:::

:::card{emoji="❓" accent="sk"}
### 缺的不是生成
缺进化与共享机制
:::

:::

---

layout: Split
chart: solution-triangle
badge: 方案
chapter: SkillClaw 介绍

## 阿里开源 SkillClaw

:::left
:::card{emoji="⭐" accent="a"}
### GitHub 1.3k Stars
开源社区认可
:::
:::

:::right
:::card{emoji="🧬" accent="c"}
### 自动进化
从对话轨迹提炼经验
:::
:::

---

layout: Takeaways
badge: 观点
chapter: 深层意义

## 群体智能的关键一步

:::takeaways

:::takeaway{icon="🧠"}
模型 → 推理能力
:::

:::takeaway{icon="💬"}
Memory → 长期上下文
:::

:::takeaway{icon="⚡"}
Skill → 行动智慧
:::

:::

---

## 让 AI 技能自动进化

<!-- 未指定 layout，role 自动推断为 closing -->

::pills
去重 :: 合并 :: 跨端共享
::
```

---

## 4. 自动排版引擎

### 4.1 内容特征提取

```typescript
interface ContentFeatures {
  hasH1: boolean;
  hasH2: boolean;
  cardCount: number;
  itemCount: number;
  takeawayCount: number;
  hasSplit: boolean;
  chartDeclared: boolean;
  codeBlockCount: number;
  pillCount: number;
  hostCount: number;
  totalTextLength: number;
}
```

### 4.2 布局推断规则

| 优先级 | 条件 | 推断布局 |
|--------|------|----------|
| 1 | `hasH1 && (pillCount > 0 || hostCount > 0)` | Cover |
| 2 | `role === 'closing'` (最后一块) | Cover |
| 3 | `takeawayCount > 0` | Takeaways |
| 4 | `hasSplit` | Split |
| 5 | `cardCount >= 3 && chartDeclared` | SlimHeader |
| 6 | `cardCount === 2` | TwoCards |
| 7 | `cardCount >= 3 && !chartDeclared` | Grid2x2 |
| 8 | `itemCount > 0` | SlimHeader |
| 9 | 兜底 | Split |

### 4.3 多样性约束算法

```typescript
function enforceDiversity(
  slides: SlideDef[],
  policy: 'diverse' | 'balanced' | 'fixed'
): SlideDef[] {
  if (policy === 'fixed') return slides;

  const LAYOUTS_CONTENT = ['Grid2x2', 'Split', 'SlimHeader', 'TwoCards', 'Takeaways'];
  const result = [...slides];

  for (let i = 0; i < result.length; i++) {
    if (result[i].role === 'cover' || result[i].role === 'closing') continue;

    if (policy === 'diverse') {
      const prev = result[i - 1]?.layout;
      const prevPrev = result[i - 2]?.layout;
      if (prev === result[i].layout && prevPrev === result[i].layout) {
        result[i].layout = pickAlternative(result[i].layout, LAYOUTS_CONTENT, [prev, prevPrev]);
      }
    }

    if (policy === 'balanced') {
      const counts = countLayouts(result.slice(0, i));
      if ((counts[result[i].layout] || 0) / i > 0.4 && i > 2) {
        result[i].layout = pickUnderrepresented(LAYOUTS_CONTENT, counts);
      }
    }
  }

  return result;
}
```

---

## 5. 主题包机制

### 5.1 目录结构

```
skills/remotion-deck/themes/
├── _registry.json            # 主题注册表
├── tech-evolve/
│   ├── theme.yaml            # 声明式 Token 定义
│   ├── styles.css            # HTML 路径的 CSS 变量
│   ├── tokens.ts             # Remotion 路径的 ThemeTokens（编译生成）
│   ├── backgrounds/
│   │   ├── orbs.tsx
│   │   └── grid-noise.tsx
│   └── animations/
│       └── default.yaml
├── risk-narrative/
│   └── ...
└── presentation-c/
    ├── theme.yaml
    ├── styles.css
    ├── tokens.ts
    ├── backgrounds/
    │   └── mesh-gradient.tsx
    └── animations/
        └── default.yaml
```

### 5.2 theme.yaml 格式

```yaml
id: presentation-c
name: Presentation C

colors:
  bg: "#050508"
  surface: "#0a0a10"
  accentA: "#6366f1"    # indigo
  accentB: "#ec4899"    # pink
  accentC: "#06b6d4"    # cyan
  # ... 完整色彩字段

fonts:
  family: '"Noto Sans SC", "PingFang SC", system-ui, sans-serif'
  serif: '"Noto Serif SC", "STSong", Georgia, serif'
  mono: '"Space Grotesk", "JetBrains Mono", monospace'

fontSizes:
  display: 130
  hero: 130
  # ... 完整字号字段

card:
  glassBlur: 20
  bg: "rgba(255,255,255,0.035)"
  border: "rgba(255,255,255,0.12)"

background: mesh-gradient    # 引用 backgrounds/ 下的策略名
animations: default           # 引用 animations/ 下的预设名
```

### 5.3 主题注册表 `_registry.json`

```json
[
  {
    "id": "tech-evolve",
    "name": "科技进化",
    "keywords": ["技术", "AI", "框架", "开源", "进化", "架构"],
    "accent": ["#22d3ee", "#4ade80", "#a78bfa"],
    "background": "orbs"
  },
  {
    "id": "risk-narrative",
    "name": "风险叙事",
    "keywords": ["安全", "风险", "事故"],
    "accent": ["#ef4444", "#f97316", "#fbbf24"],
    "background": "orbs"
  },
  {
    "id": "presentation-c",
    "name": "Presentation C",
    "keywords": ["演示", "产品", "对比", "发布"],
    "accent": ["#6366f1", "#ec4899", "#06b6d4"],
    "background": "mesh-gradient"
  }
]
```

主题选择逻辑：
1. `theme:` frontmatter 强制指定 — 最高优先
2. 内容关键词匹配 `_registry.json` 的 `keywords` — 语义推荐
3. 兜底：`tech-evolve`

---

## 6. 图表即代码

### 6.1 语义类型映射（Phase 1）

取代正则模糊匹配，使用显式图表 ID 映射：

| 图表 ID | 语义类型 | 适用场景 |
|---------|----------|----------|
| `cover-helix` | 进化/循环 | 封面装饰 |
| `pain-fork` | 痛点分叉 | 问题拆解 |
| `solution-triangle` | 方案三角 | 解决方案 |
| `architecture` | 架构分层 | 系统架构 |
| `dual-engine` | 双引擎对比 | 并行方案 |
| `memory-compare` | 记忆对比 | 对比分析 |
| `share-network` | 共享网络 | 网络拓扑 |
| `steps` | 步骤流程 | 流程步骤 |
| `pyramid` | 金字塔递进 | 层级递进 |

Phase 1 声明方式：`chart: memory-compare`，编译器直接映射为 `page.diagramKey`。

### 6.2 图表数据绑定（Phase 1.5）

```typescript
interface DiagramProps {
  width?: number;
  height?: number;
  data?: Record<string, unknown>;  // 结构化数据
}
```

```markdown
---
chart: memory-compare
chart-data:
  leftLabel: 事实记忆
  rightLabel: 行动记忆
  leftItems: ["记住发生了什么", "被动记录"]
  rightItems: ["学会下次该怎么做", "主动进化"]
---
```

### 6.3 Mermaid 集成（Phase 2）

**取舍**：

| 维度 | Mermaid | 自定义 DSL |
|------|---------|------------|
| 学习成本 | 低 | 高 |
| 图表覆盖 | 广 | 窄 |
| 渲染灵活性 | 低（SVG 固定） | 高（可自定义） |
| 动画支持 | 无 | 可控 |
| 视觉一致性 | 差（不联通主题） | 好（消费 ThemeTokens） |

Phase 2 方案：Mermaid 子集 + 主题适配层
1. 支持 `graph` / `sequenceDiagram` / `classDiagram` 三种子集
2. `mermaid.render()` 生成 SVG
3. 后处理 SVG：替换颜色/字号为 ThemeTokens

---

## 7. 编译管线

### 7.1 完整流程

```
deck.md
   │
   ▼  [markdown-parser]
SlideAst[]
   │
   ▼  [layout-engine]
SlideDef[] (layout + 多样性约束)
   │
   ▼  [content-mapper]
content-slabs.json  ──────────────┐
   │                              │
   ▼  [timing-resolver]           ▼  [html-generator]
page-splits.json               presentation.html
   │
   ▼  [bridge-adapter]
remotion-data.json (项目目录)
   │
   ▼  [remotion render / preview / still]
MP4 / PNG
```

### 7.2 编译器模块

```
skills/remotion-deck/
├── markdown-compiler/
│   ├── index.ts              # CLI 入口
│   ├── parser.ts             # markdown-parser（remark 插件）
│   ├── layout-engine.ts      # 自动排版引擎
│   ├── content-mapper.ts     # SlideDef → content-slabs.json
│   ├── timing-resolver.ts    # SRT/WAV → wav-durations.json
│   └── types.ts              # 编译器类型定义
```

### 7.3 CLI 新增子命令

```bash
node cli.cjs compile --input <deck.md> --output <project-dir>
```

向后兼容：现有 `node cli.cjs bridge --project <dir>` 保持不变。`compile` 是新增路径。

---

## 8. 与上游集成

### 8.1 srt-to-deck 适配

**模式 A（现有）**：SRT → content-slabs.json + presentation.html
**模式 B（新增）**：SRT → deck.md → deck-compile → content-slabs.json + remotion-data.json

srt-to-deck 核心逻辑（SRT 解析和语义分页）不涉及输出格式变更，适配成本低。

### 8.2 时序同步

```
deck.md 中的 audio/srt 声明
    │
    ▼
timing-resolver 读取 SRT/WAV
    │
    ▼
wav-durations.json + page-splits.json
    │
    ▼
bridge-adapter → remotion-data.json（帧级时序精确）
```

Phase 1 卡片和条目的 `appearSec` 默认均匀分布。Phase 2 增加页面级 appear-at 声明：

```markdown
:::card{emoji="📦" appear-at="3.5s"}
### 技能膨胀
:::
```

---

## 9. 数据隔离方案

### 9.1 天然隔离

每个项目对应一个独立 `.md` 文件，产出物全写入项目目录：

```
features/content-pipeline/skillclaw-mid-video/
├── production/
│   ├── deck.md                    # 源文件
│   ├── timing/
│   │   ├── content-slabs.json
│   │   ├── remotion-data.json     # 项目级，不写入 public/
│   │   └── wav-durations.json
│   └── slides/
│       └── presentation.html

features/content-pipeline/anthropic-tips-mid-video/
├── production/
│   ├── deck.md
│   ├── timing/
│   │   └── remotion-data.json     # 独立文件，互不影响
```

### 9.2 Remotion 数据加载适配

`render.cjs` 在执行时设置 `REMOTION_DATA_PATH` 环境变量，或将项目级文件符号链接到 `public/remotion-data.json`。

`generated-meta.ts` 改为在 `calculateMetadata` 回调中从 `remotion-data.json` 动态读取，不再覆写全局文件。

---

## 10. 迁移策略

### 10.1 分阶段

| 阶段 | 内容 | 影响 |
|------|------|------|
| Phase 0 | 编译器 MVP：markdown-parser + layout-engine + content-mapper | 新增代码，不影响现有功能 |
| Phase 1 | 主题包重构 + 数据隔离 + CLI 适配 | 替换 themes/ + bridge 输出路径 |
| Phase 1.5 | 图表数据绑定 + srt-to-deck 输出 Markdown | 扩展现有接口 |
| Phase 2 | Mermaid 子集 + appear-at 声明式 + html-generator | 扩展功能 |

### 10.2 向后兼容

- 现有 content-slabs.json 仍可被 bridge 正常消费
- 现有 remotion-data.json 格式不变
- 6 个布局组件接口不变
- 9 个图表组件接口不变
- 新增 `compile` 子命令是平行路径，不破坏现有流程
- 两个不同项目先后 compile + render 不会互相覆盖

### 10.3 迁移工具

提供 `json-to-md` 反向转换工具，Phase 0-1 期间 JSON 和 Markdown 双轨并存。

---

## 11. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Markdown 解析器不一致 | `:::card{}` 等自定义指令在不同渲染器中表现不同 | 中 | 使用 remark 统一解析；提供 `deck lint` 校验命令 |
| 自动排版产出不可预期 | 用户不了解 layout 被自动调整 | 高 | 编译器输出 `deck-compile-report.json`，记录布局来源和调整原因 |
| Mermaid SVG 不兼容 | 颜色/字号/alpha 不满足 Headless Chrome | 高（Phase 2） | PostCSS-like 修正层；Phase 1 先用精确 ID 避开 |
| Remotion staticFile 机制限制 | 只从 `public/` 加载 | 中 | 编译时复制到 `public/` + `REMOTION_DATA_PATH` 环境变量 |
| Markdown schema 校验难 | 类型错误在编译时才暴露 | 中 | JSON Schema for frontmatter + `deck lint` + VS Code YAML 扩展 |
| 多样性约束过激 | 强制换布局导致内容不匹配 | 中 | `layout-policy: fixed` 关闭自动调整 + 被调整布局在报告中标注 |
| 现有项目升级成本 | 已有 content-slabs.json 需迁移 | 低 | `json-to-md` 反向工具 + 双轨并存 |
| 旧 svgHint 失效 | 现有 content-slabs.json 的 svgHint 无法映射 | 低 | bridge 阶段保底：先查 diagramKey，未命中走旧正则 |