# Deck Engine 抽象层设计 Spec

| 字段 | 值 |
|------|------|
| 日期 | 2026-05-22 |
| 状态 | draft |
| 归属 skill | `skills/remotion-deck` |
| 影响范围 | `cli.cjs`, `lib/remotion_bridge.cjs`, `lib/render.cjs`, `src/types.ts`, `src/theme.ts`, `src/themes/*`, `src/Video.tsx`, `src/diagrams/registry.ts`, `src/lib/data_loader.ts` |
| 前置依赖 | 现有 remotion-deck 帧级渲染管线，srt-to-deck content-slabs 数据格式 |

---

## 1. 目标与范围

### 1.1 解决的问题

| 问题 | 根因 | 本方案如何解决 |
|------|------|---------------|
| **视觉同质化**：不同话题的视频产出几乎一样 | 布局分配硬编码（按顺序循环），主题只换颜色不换排版，图表种类有限(9个) | Deck Manifest 声明式配置布局权重+排版变体+图表策略；布局分配器引入多样性算法 |
| **数据覆盖**：`public/remotion-data.json` 被第二次生成覆盖 | render.cjs `fs.copyFileSync(dataPath, publicDataPath)` 写入固定路径 | 数据隔离：每个 project 的 remotion-data.json 留在 `<project>/timing/` 下，通过符号链接指向 |
| **布局分配固定**：没有多样性约束 | `remotion_bridge.cjs` 直接透传 content-slabs 的 `layout` 字段，无分配逻辑 | 布局分配器：权重+必选+不重复约束 |
| **图表匹配粗糙**：svgHint 只支持 9 种预定义图表 | `registry.ts` `KEYWORD_MAP` 仅 9 条正则 | 扩展图表策略：精确匹配+语义匹配双模式，图表域(domain)分类 |

### 1.2 不解决的问题

| 不做的事 | 原因 |
|----------|------|
| 不做 WYSIWYG 编辑器 | 本方案是声明式配置驱动，不是可视化编辑 |
| 不改变 Remotion 渲染管线本身 | Remotion Composition 入口不变，只改变数据供给方式 |
| 不做实时预览的 Manifest 热更新 | Manifest 是构建时配置，运行时只读 |
| 不做 CSS-in-JS 主题运行时 | 主题 Token 在构建时固化到 remotion-data.json，运行时不切换 |
| 不做 SVG 图表自动生成 | 新增图表仍需手工编写 React 组件，Manifest 只负责匹配和选择 |

---

## 2. 核心概念

### 2.1 Deck Manifest

每个视频项目的模板配置文件（YAML 格式），声明本项目的主题、布局分配规则、图表策略、排版变体。位于 `<project>/timing/deck-manifest.yaml`。

**核心定位**：把现在硬编码在 `remotion_bridge.cjs` 和 `registry.ts` 的决策逻辑，提升为可配置、可版本化的声明式文件。

```
deck-manifest.yaml  ←  决策配置
        │
        ▼
srt-to-deck / remotion_bridge  ←  读取配置，执行决策
        │
        ▼
remotion-data.json  ←  决策结果（含 layout/diagramKey/layoutVariant 字段）
        │
        ▼
remotion-deck (engine mode)  ←  读取结果，执行渲染
```

### 2.2 布局分配器 (Layout Allocator)

替代当前 content-slabs.json 直接指定 `layout` 字段的方式。引入权重+多样性约束算法，为每个页面自动选择布局，确保：

- 封面页必选 Cover，收尾页必选 Cover/Takeaways
- 相邻页面不重复同一布局
- 布局使用频率与权重成正比
- 可选布局白名单限制了该项目的布局池

### 2.3 主题引擎 v2 (Theme Engine v2)

在当前 `ThemeTokens`（仅含色彩、字号、间距、圆角、卡片）基础上，扩展为包含：

- **排版变体 (typography variant)**：紧凑/舒展/杂志风，控制标题层级比例、行高、字符间距
- **卡片样式变体 (card variant)**：glass/flat/bordered/minimal，控制卡片的视觉风格
- **背景策略 (background strategy)**：solid/gradient/mesh/webgl，控制 SlideShell 的背景渲染
- **动画风格 (animation style)**：calm/energetic/cinematic，控制 Appear 组件的 spring 参数和时序

### 2.4 图表策略 (Diagram Strategy)

图表选择的双模式机制：

- **精确匹配 (exact)**：svgHint 值直接对应 diagramKey，无歧义
- **语义匹配 (semantic)**：根据 content-slabs 的 `role` + `heading` + `svgHint` 关键词，在图表域(domain)中查找最合适的图表

图表按"语义域"分类，每个域对应一类内容场景（process/compare/structure/growth/decision/knowledge/abstract/temporal/narrative）。

---

## 3. Deck Manifest 设计

### 3.1 完整 YAML Schema

```yaml
# deck-manifest.yaml — Deck Engine 模板清单
# 位于 <project>/timing/deck-manifest.yaml

# ─── 元信息 ───
version: 1                        # Manifest schema 版本
name: "anthropic-next-gen-claude"  # 项目标识（用于日志和归档）
description: "Anthropic 下一代 Claude 八条干货"  # 人类可读描述

# ─── 主题配置 ───
theme:
  id: "presentation-c"            # ThemeTokens v2 的 ID（引用 themes/ 目录）
  variant: "magazine"             # 排版变体：compact | relaxed | magazine
  cardStyle: "glass"              # 卡片风格：glass | flat | bordered | minimal
  background: "mesh"              # 背景策略：solid | gradient | mesh | webgl
  animation: "calm"               # 动画风格：calm | energetic | cinematic

# ─── 布局配置 ───
layout:
  # 允许的布局及其权重（权重越高越优先）
  allowed:
    Cover: { weight: 0, role: [cover, closing] }  # weight=0 表示仅由角色强制分配
    Grid2x2: { weight: 3 }
    Split: { weight: 4 }
    SlimHeader: { weight: 3 }
    TwoCards: { weight: 3 }
    Takeaways: { weight: 2, role: [closing] }     # Takeaways 倾向于收尾页使用

  # 多样性约束
  diversity:
    maxConsecutive: 2              # 最多连续 N 页同一布局（默认 2）
    minUniqueLayouts: 3            # 整份 deck 至少 N 种不同布局（不含 Cover）
    mustUseBefore:                 # 必须在前 N 页内使用的布局
      - { layout: Split, before: 5 }
      - { layout: Grid2x2, before: 7 }

  # 角色固定映射（不可被分配器覆盖）
  roleBinding:
    cover: Cover                   # role=cover 的页面固定使用 Cover 布局
    closing: [Cover, Takeaways]    # role=closing 的页面在 Cover 和 Takeaways 中选择

# ─── 图表策略 ───
diagrams:
  mode: "semantic"                # exact | semantic
  # 语义匹配时的领域-图表映射
  domainMap:
    process: [steps, flow-arrows, pipeline]    # 流程类
    compare: [memory-compare, dual-engine, split-fork]  # 对比类
    structure: [architecture, layer-stack, module-grid]  # 结构类
    growth: [cover-helix, growth-curve, milestone-timeline]  # 成长类
    decision: [pain-fork, solution-triangle, decision-tree]  # 决策类
    knowledge: [share-network, knowledge-graph, tree-map]  # 知识类
    abstract: [pyramid, concentric-rings, radar-chart]  # 抽象概念类
    temporal: [timeline, sprint-board, gantt]  # 时间类
    narrative: [story-arc, cause-effect, dialogue-bubble]  # 叙事类

  # svgHint 关键词到域的映射（语义匹配使用）
  hintToDomain:
    # 中文关键词
    "进化|螺旋|齿轮|生长": growth
    "痛点|三叉|问题|苦": decision
    "方案|三角|解决|对策": decision
    "架构|分层|模块|系统|栈": structure
    "引擎|流水线|Pipeline": process
    "记忆|对比|事实|vs": compare
    "共享|网络|孤岛|图": knowledge
    "步骤|流程|顺序|上手": process
    "金字塔|递进|层级": abstract
    "时间线|年代|里程碑": temporal
    "循环|闭环|反馈": process
    "文档|文件|知识库": knowledge
    "闪电|速度|效率": growth
    "门|分叉|选择": decision
    "面具|性格|多面": abstract
    "人脑|思考|产品思维": abstract
    "睡眠|做梦|整理": narrative
    "问号|哲学|意识": abstract
    # 英文关键词
    "helix|evolution|growth": growth
    "fork|pain|problem": decision
    "solution|triangle": decision
    "architecture|layer|stack": structure
    "engine|pipeline|flow": process
    "memory|compare|vs": compare
    "network|island|graph": knowledge
    "steps|process|sequence": process

  # 同域内图表不重复策略
  deduplication: true              # 同一视频内，同域优先选不同图表

  # 未知 svgHint 的兜底图表
  fallback: "pyramid"              # 无法匹配时的默认图表

# ─── 数据隔离 ───
project:
  id: "anthropic-next-gen-claude-eight-tips-mid-video"  # 全链路项目 ID
  # 不再写入 public/remotion-data.json，改为：
  # 1. remotion-data.json 保留在 <project>/timing/ 下
  # 2. 通过 REMOTION_DATA_PATH 环境变量指向
  # 3. render/preview/still 启动前创建符号链接

# ─── 全局覆盖（可选） ───
overrides:
  # 针对特定页面号手动指定布局和图表（优先级最高）
  pages:
    0:                             # pageId=0
      layout: Cover                # 强制布局
      diagramKey: cover-helix      # 强制图表
    8:
      layout: Takeaways
      diagramKey: pyramid
```

### 3.2 Manifest 加载优先级

```
1. <project>/timing/deck-manifest.yaml    ← 项目级配置（最高优先）
2. skills/remotion-deck/manifest-defaults.yaml  ← 全局默认配置
3. 硬编码回退值                            ← 代码中的兜底逻辑
```

加载逻辑（在 `remotion_bridge.cjs` 中实现）：

```javascript
function loadManifest(projectDir, skillDir) {
  const projectManifest = readYaml(path.join(projectDir, 'timing', 'deck-manifest.yaml'));
  const defaultManifest = readYaml(path.join(skillDir, 'manifest-defaults.yaml'));
  if (!projectManifest) return defaultManifest || MANIFEST_HARDCODED_DEFAULTS;
  return deepMerge(defaultManifest, projectManifest);  // 项目配置覆盖默认值
}
```

---

## 4. 布局分配器算法

### 4.1 输入

- `pages`: content-slabs.json 中的 pages 数组（含 pageId, role, heading 等字段）
- `manifest.layout`: Deck Manifest 中的布局配置

### 4.2 算法伪代码

```
function allocateLayouts(pages, layoutConfig):
  allowed = layoutConfig.allowed           # { Cover: {weight, role}, ... }
  diversity = layoutConfig.diversity       # { maxConsecutive, minUniqueLayouts, mustUseBefore }
  roleBinding = layoutConfig.roleBinding   # { cover: "Cover", closing: ["Cover","Takeaways"] }
  overrides = layoutConfig.overrides?.pages  # 手动覆盖

  result = []                              # [{pageId, layout, source}]
  usedLayouts = Set()                      # 已使用的布局集合
  lastLayout = null                        # 上一页的布局
  consecutiveCount = 0                     # 连续同一布局的计数

  for each page in pages:
    # 1. 检查手动覆盖
    if overrides and overrides[page.pageId]:
      result.push({pageId: page.pageId, layout: overrides[page.pageId].layout, source: 'override'})
      usedLayouts.add(overrides[page.pageId].layout)
      continue

    # 2. 角色固定映射
    if page.role in roleBinding:
      roleLayouts = roleBinding[page.role]
      if isArray(roleLayouts):
        unused = roleLayouts.filter(l => !usedLayouts.has(l))
        chosen = unused.length > 0 ? unused[0] : roleLayouts[0]
      else:
        chosen = roleLayouts
      result.push({pageId: page.pageId, layout: chosen, source: 'role-binding'})
      usedLayouts.add(chosen)
      lastLayout = chosen
      consecutiveCount = (chosen === lastLayout) ? consecutiveCount + 1 : 1
      continue

    # 3. 候选布局池（排除角色绑定的布局）
    candidates = Object.entries(allowed)
      .filter(([name, cfg]) => !cfg.role)
      .filter(([name, cfg]) => name !== lastLayout || consecutiveCount < diversity.maxConsecutive)
      .map(([name, cfg]) => ({name, weight: cfg.weight}))

    # 4. 权重调整
    for each candidate in candidates:
      # 4a. 使用次数少的布局权重加成（促进多样性）
      timesUsed = countInArray(result.map(r => r.layout), candidate.name)
      candidate.weight *= (1 + 0.5 / (1 + timesUsed))

      # 4b. mustUseBefore 约束加成
      for each mustRule in diversity.mustUseBefore:
        if mustRule.layout === candidate.name and page.pageId < mustRule.before:
          if !usedLayouts.has(candidate.name):
            candidate.weight *= 3.0

      # 4c. 内容适配度
      candidate.weight *= contentFitScore(page, candidate.name)

    # 5. 加权随机选择
    totalWeight = sum(candidates.map(c => c.weight))
    rand = random() * totalWeight
    cumulative = 0
    chosen = candidates[0].name
    for each candidate in candidates:
      cumulative += candidate.weight
      if rand <= cumulative:
        chosen = candidate.name
        break

    # 6. 更新状态
    result.push({pageId: page.pageId, layout: chosen, source: 'allocator'})
    usedLayouts.add(chosen)
    consecutiveCount = (chosen === lastLayout) ? consecutiveCount + 1 : 1
    lastLayout = chosen

  return result
```

### 4.3 内容适配度评分

```
function contentFitScore(page, layoutName):
  score = 1.0

  cardCount = (page.cards?.length || 0) + (page.leftCards?.length || 0) + (page.rightCards?.length || 0)
  if layoutName === "Grid2x2" and cardCount === 4: score *= 2.0
  if layoutName === "Grid2x2" and cardCount !== 4: score *= 0.3
  if layoutName === "TwoCards" and cardCount === 2: score *= 2.0
  if layoutName === "TwoCards" and cardCount > 3: score *= 0.3
  if layoutName === "Split" and page.leftCards and page.rightCards: score *= 2.0
  if layoutName === "Split" and not page.leftCards: score *= 0.4
  if layoutName === "SlimHeader" and page.items and page.items.length >= 3: score *= 2.0
  if layoutName === "Takeaways" and page.takeaways: score *= 2.0
  if page.svgHint and layoutName in ["Split", "TwoCards", "SlimHeader"]: score *= 1.3

  return score
```

### 4.4 与现有 content-slabs.layout 的关系

当前 content-slabs.json 的 `layout` 字段是 srt-to-deck 产出的"推荐值"。Deck Engine 引入布局分配器后：

- 如果 Manifest 存在 `layout.allowed`，分配器的结果覆盖 content-slabs 的 `layout`
- 如果 Manifest 不存在（向后兼容），content-slabs 的 `layout` 透传使用
- Manifest `overrides.pages` 的手动覆盖优先级最高

---

## 5. 主题引擎 v2 设计

### 5.1 ThemeTokens v2 完整结构

```typescript
export interface ThemeTokensV2 {
  id: string;
  name: string;
  version: 2;

  /* ─── 色彩（与 v1 相同） ─── */
  bg: string;
  surface: string;
  surface2: string;
  text1: string;
  text2: string;
  accentA: string;
  accentB: string;
  accentC: string;
  sky?: string;
  danger?: string;
  green?: string;
  orange?: string;
  indigoRgb?: string;
  pinkRgb?: string;
  cyanRgb?: string;
  glassHighlight?: string;

  /* ─── 字体（与 v1 相同） ─── */
  fontFamily: string;
  fontSerif: string;
  fontMono: string;

  /* ─── 字号（与 v1 相同，1920x1080） ─── */
  fsDisplay: number;
  fsHero: number;
  fsXl: number;
  fsLg: number;
  fsTitle: number;
  fsSubtitle: number;
  fsBody: number;
  fsBodySm: number;
  fsCardTitle: number;
  fsTimeline: number;
  fsLabel: number;
  fsCaption: number;
  fsChrome: number;
  fsPill: number;
  fsStat: number;
  fsMono: number;
  fsTable: number;

  /* ─── 间距（与 v1 相同） ─── */
  spXs: number;
  spSm: number;
  spMd: number;
  spLg: number;
  spXl: number;
  sp2Xl: number;

  /* ─── 圆角（与 v1 相同） ─── */
  rSm: number;
  rMd: number;
  rLg: number;

  /* ─── 卡片（与 v1 相同） ─── */
  glassBlur: number;
  cardBg: string;
  cardBorder: string;
  cardBorderHover: string;

  /* ═══ v2 新增 ═══ */

  /* ─── 排版变体 ─── */
  typography: {
    variant: 'compact' | 'relaxed' | 'magazine';
    headingLineHeight: number;      // compact=1.05, relaxed=1.15, magazine=1.2
    bodyLineHeight: number;         // compact=1.35, relaxed=1.5, magazine=1.6
    headingLetterSpacing: number;   // compact=-0.02, relaxed=0, magazine=0.02
    bodyLetterSpacing: number;      // compact=0, relaxed=0.01, magazine=0.02
    paragraphSpacing: number;       // compact=16, relaxed=24, magazine=32
    headingTransform: 'none' | 'uppercase';
  };

  /* ─── 卡片样式变体 ─── */
  cardVariant: {
    style: 'glass' | 'flat' | 'bordered' | 'minimal';
    padding: string;
    shadow: string;
    borderStyle: string;
    backgroundStyle: string;
  };

  /* ─── 背景策略 ─── */
  background: {
    strategy: 'solid' | 'gradient' | 'mesh' | 'webgl';
    gradientAngle?: number;
    gradientStops?: Array<{offset: number; color: string}>;
    meshBlobs?: Array<{
      x: number; y: number; r: number;
      phase: number; speedX: number; speedY: number; speedR: number;
      h: number; s: number; l: number;
    }>;
    meshPulseIntensity?: number;
    webglShader?: string;
  };

  /* ─── 动画风格 ─── */
  animation: {
    style: 'calm' | 'energetic' | 'cinematic';
    springConfig: {
      damping: number;              // calm=18, energetic=10, cinematic=14
      stiffness: number;            // calm=80, energetic=160, cinematic=120
      mass: number;                 // calm=1.0, energetic=0.6, cinematic=0.8
    };
    appearDuration: number;         // calm=24, energetic=12, cinematic=18
    staggerDelay: number;           // calm=12, energetic=6, cinematic=10
    progressStyle: 'glow' | 'gradient' | 'thin';
  };
}
```

### 5.2 v1 与 v2 对比

| 维度 | v1 (当前) | v2 (新增) |
|------|-----------|-----------|
| 色彩 | 完整 | 完整（不变） |
| 字号 | 完整 | 完整（不变） |
| 间距/圆角 | 完整 | 完整（不变） |
| 排版规则 | 无（硬编码在各组件中） | `typography` 块：行高/字间距/段间距/标题样式 |
| 卡片样式 | `glassCard()` 硬编码两套 | `cardVariant` 块：4 种风格声明式切换 |
| 背景策略 | `SlideShell` 硬编码两套 | `background` 块：4 种策略声明式切换 |
| 动画风格 | `Appear` 硬编码 spring 参数 | `animation` 块：3 种风格声明式切换 |
| 主题差异化 | 仅颜色不同 | 颜色 + 排版 + 卡片 + 背景 + 动画 五维差异 |

### 5.3 createTheme() 扩展

```typescript
export function createTheme(tokens: ThemeTokensV2 | ThemeTokens): Theme {
  const t = migrateToV2(tokens);

  function glassCard(accent?: string, glow = false): React.CSSProperties {
    switch (t.cardVariant.style) {
      case 'glass': return buildGlassCard(t, accent, glow);
      case 'flat': return buildFlatCard(t, accent, glow);
      case 'bordered': return buildBorderedCard(t, accent, glow);
      case 'minimal': return buildMinimalCard(t, accent, glow);
    }
  }
}

function migrateToV2(tokens: ThemeTokensV2 | ThemeTokens): ThemeTokensV2 {
  if ('version' in tokens && tokens.version === 2) return tokens;
  return {
    ...tokens,
    version: 2,
    typography: { variant: 'relaxed', ...DEFAULT_TYPOGRAPHY },
    cardVariant: { style: 'glass', ...DEFAULT_CARD_VARIANT },
    background: { strategy: tokens.id === 'presentation-c' ? 'mesh' : 'gradient' },
    animation: { style: 'calm', ...DEFAULT_ANIMATION },
  };
}
```

### 5.4 排版变体的具体数值

| 属性 | compact | relaxed | magazine |
|------|---------|---------|----------|
| headingLineHeight | 1.05 | 1.08 | 1.20 |
| bodyLineHeight | 1.35 | 1.45 | 1.60 |
| headingLetterSpacing | -0.02em | 0 | 0.02em |
| bodyLetterSpacing | 0 | 0.01em | 0.02em |
| paragraphSpacing | 16px | 20px | 32px |
| headingTransform | none | none | uppercase |
| 标题字号缩放因子 | 0.9 | 1.0 | 1.1 |
| 正文字号缩放因子 | 0.85 | 1.0 | 1.0 |
| 内容区内边距 | 40px 72px | 40px 72px | 56px 80px |

### 5.5 背景策略的渲染逻辑

```typescript
function renderBackground(theme: ThemeTokensV2): React.ReactNode {
  switch (theme.background.strategy) {
    case 'solid':
      return <div style={{ background: theme.bg }} />;
    case 'gradient':
      return <GradientBg theme={theme} />;
    case 'mesh':
      return <MeshGradientBg pulseIntensity={theme.background.meshPulseIntensity ?? 0.15} />;
    case 'webgl':
      return <WebGLBg shader={theme.background.webglShader} />;
  }
}
```

---

## 6. 图表策略设计

### 6.1 双模式机制

```typescript
export function resolveDiagram(
  svgHint: string | null | undefined,
  page: PageData,
  diagramConfig: DiagramConfig,
  usedDiagrams: Set<string>
): DiagramComponent | null {
  if (!svgHint) return null;

  // 模式 1：精确匹配
  if (diagramConfig.mode === 'exact') {
    if (DIAGRAM_MAP[svgHint]) return DIAGRAM_MAP[svgHint];
    return null;
  }

  // 模式 2：语义匹配
  if (DIAGRAM_MAP[svgHint]) return DIAGRAM_MAP[svgHint];

  const domain = resolveDomain(svgHint, diagramConfig.hintToDomain);
  if (!domain) return DIAGRAM_MAP[diagramConfig.fallback] || null;

  const candidates = (diagramConfig.domainMap[domain] || [])
    .filter(key => DIAGRAM_MAP[key])
    .filter(key => diagramConfig.deduplication ? !usedDiagrams.has(key) : true);

  if (candidates.length === 0) {
    const allAvailable = Object.keys(DIAGRAM_MAP).filter(key => !usedDiagrams.has(key));
    if (allAvailable.length === 0) return DIAGRAM_MAP[diagramConfig.fallback] || null;
    return DIAGRAM_MAP[allAvailable[0]];
  }

  return DIAGRAM_MAP[candidates[0]];
}
```

### 6.2 图表扩展路标

**Phase 1（当前）**：9 个图表

**Phase 2（扩展到 15）**：新增 6 个

| 新增图表 ID | 域 | 说明 |
|-------------|----|------|
| `flow-arrows` | process | 流程箭头图 |
| `layer-stack` | structure | 分层栈图 |
| `growth-curve` | growth | 增长曲线图 |
| `decision-tree` | decision | 决策树图 |
| `timeline` | temporal | 时间线图 |
| `cause-effect` | narrative | 因果关系图 |

**Phase 3（扩展到 20+）**：新增 5+

| 新增图表 ID | 域 | 说明 |
|-------------|----|------|
| `split-fork` | compare | 分叉对比图 |
| `module-grid` | structure | 模块网格图 |
| `concentric-rings` | abstract | 同心环图 |
| `radar-chart` | abstract | 雷达图 |
| `knowledge-graph` | knowledge | 知识图谱图 |

**Phase 4（远期）**：图表组件接收 `diagramData` 参数，从 content-slabs 提取的实际数据自动生成标注文字。

```typescript
interface DiagramProps {
  width?: number;
  height?: number;
  data?: Record<string, unknown>;  // 结构化数据
  theme?: Theme;                   // 主题注入
}
```

---

## 7. 数据隔离方案

### 7.1 当前问题

`render.cjs` 中 `fs.copyFileSync(dataPath, publicDataPath)` 写入固定路径，多项目互相覆盖。

### 7.2 方案：符号链接替代文件复制

```javascript
function linkProjectData(projectDir, skillDir) {
  const dataPath = path.join(absProject, 'timing', 'remotion-data.json');
  const linkPath = path.join(skillDir, 'public', 'remotion-data.json');

  if (fs.existsSync(linkPath) || fs.lstatSync(linkPath).isSymbolicLink()) {
    fs.unlinkSync(linkPath);
  }

  fs.symlinkSync(dataPath, linkPath);
  console.log(`🔗 Linked: ${dataPath} → ${linkPath}`);
}
```

CLI `--project` 参数强制必需，缺失时报错。

### 7.3 RemotionData v2 格式

```typescript
export interface RemotionDataV2 {
  version: 2;
  projectId: string;            // 项目 ID，用于日志溯源
  manifestHash: string;         // deck-manifest.yaml 内容哈希
  title: string;
  themeId: string;
  themeOverrides?: Partial<ThemeTokensV2>;
  fps: number;
  width: number;
  height: number;
  totalFrames: number;
  totalDurationMs: number;
  pages: PageDataV2[];
  railLabels: RailLabels;
}

export interface PageDataV2 extends PageData {
  layoutSource: 'override' | 'role-binding' | 'allocator' | 'content-slabs';
  diagramKey: string;           // 从可选改为必需（无图表时为 "none"）
  diagramDomain?: string;
  layoutVariant?: string;
}
```

---

## 8. 全管线影响

### 8.1 srt-to-deck 改动

| 文件/模块 | 改动 | 说明 |
|-----------|------|------|
| Step 3 (内容板生成) | 新增 deck-manifest.yaml 生成引导 | Agent 在生成 content-slabs.json 后，提示创建 deck-manifest.yaml |
| content-slabs.json `layout` 字段 | 语义变更 | 从"最终布局"变为"推荐布局"，可被覆盖 |
| content-slabs.json 新增 `diagramDomain` | 可选 | 标注图表语义域 |

### 8.2 html-video-from-slides 改动

| 文件/模块 | 改动 | 说明 |
|-----------|------|------|
| `assets/themes/` | 新增排版变体 CSS | 每个主题目录扩展 typography 变体 |
| deck_assemble.js | 读取 Manifest | 用 Manifest 配置驱动 HTML 装配 |

### 8.3 remotion-deck 改动汇总

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `cli.cjs` | 修改 | --project 强制必需，新增 --manifest |
| `lib/remotion_bridge.cjs` | 重大修改 | 加载 Manifest，执行布局分配器，执行图表策略，输出 V2 |
| `lib/render.cjs` | 修改 | 符号链接替代文件复制 |
| `src/types.ts` | 扩展 | 新增 v2 类型，旧类型保留 |
| `src/theme.ts` | 修改 | v2 支持 + migrateToV2() |
| `src/Video.tsx` | 修改 | 读取 v2 字段 |
| `src/themes/*.ts` | 扩展 | 新增 v2 字段 |
| `src/diagrams/registry.ts` | 重大修改 | 双模式 + 域映射 + 去重 |
| `src/diagrams/*.tsx` | 新增 | Phase 2/3 图表组件 |
| `src/lib/data_loader.ts` | 修改 | 支持 V2 格式 |
| `src/components/SlideShell.tsx` | 修改 | background.strategy 分支 |
| `src/components/*.tsx` | 修改 | 读取 theme.typography |
| `manifest-defaults.yaml` | 新增 | 全局默认配置 |
| `src/lib/manifest_loader.ts` | 新增 | YAML 解析/校验/合并 |

---

## 9. 迁移策略

### 9.1 向后兼容原则

- v1 数据格式继续可用：无 Manifest 时降级到 v1 行为
- v1 主题继续可用：`ThemeTokens` 自动迁移为 `ThemeTokensV2`
- content-slabs.layout 继续可用：无 Manifest 时直接透传
- svgHint 精确匹配继续可用

### 9.2 分阶段迁移

**阶段 1（基础设施）**：Manifest 加载 + v2 类型 + 符号链接 + migrateToV2()
**阶段 2（布局分配器）**：allocateLayouts() + Manifest.layout 解析
**阶段 3（图表策略）**：resolveDiagram() 双模式 + 新增 6 个图表
**阶段 4（主题引擎 v2）**：排版变体 + 卡片变体 + 背景策略 + 动画风格
**阶段 5（全链路集成）**：srt-to-deck + html-video-from-slides 适配

### 9.3 回退策略

每个阶段独立可回退：删除 Manifest 文件即可回到 v1 行为。

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Manifest 解析错误导致渲染卡死 | 中 | 高 | 严格 schema 校验 + 回退到 v1 |
| 布局分配器产出不直觉 | 高 | 中 | `overrides.pages` 手动覆盖 + `layoutSource` 记录来源 |
| 语义匹配选错图表 | 中 | 中 | `diagrams.mode: "exact"` 回退 + overrides 手动指定 |
| 主题 v2 与现有不兼容 | 低 | 高 | migrateToV2() 自动填充 + 联合类型 |
| 符号链接在 Windows 失败 | 中 | 中 | 回退到文件复制 + 内容哈希校验 |
| 图表扩展增大 bundle | 低 | 低 | Remotion code splitting + 未知 key 跳过渲染 |

---

## 附录 A：manifest-defaults.yaml 全局默认配置

```yaml
version: 1
name: "default"
description: "Default manifest when no project-level manifest exists"

theme:
  id: "tech-evolve"
  variant: "relaxed"
  cardStyle: "glass"
  background: "gradient"
  animation: "calm"

layout:
  allowed:
    Cover: { weight: 0, role: [cover, closing] }
    Grid2x2: { weight: 3 }
    Split: { weight: 4 }
    SlimHeader: { weight: 3 }
    TwoCards: { weight: 3 }
    Takeaways: { weight: 2, role: [closing] }
  diversity:
    maxConsecutive: 2
    minUniqueLayouts: 3
    mustUseBefore: []
  roleBinding:
    cover: Cover
    closing: [Cover, Takeaways]

diagrams:
  mode: "semantic"
  domainMap:
    process: [steps]
    compare: [memory-compare, dual-engine]
    structure: [architecture]
    growth: [cover-helix]
    decision: [pain-fork, solution-triangle]
    knowledge: [share-network]
    abstract: [pyramid]
    temporal: []
    narrative: []
  hintToDomain:
    "进化|螺旋|齿轮|生长": growth
    "痛点|三叉|问题|苦": decision
    "架构|分层|模块|系统|栈": structure
    "引擎|流水线|Pipeline": process
    "记忆|对比|事实|vs": compare
    "共享|网络|孤岛|图": knowledge
    "步骤|流程|顺序|上手": process
    "金字塔|递进|层级": abstract
  deduplication: true
  fallback: "pyramid"

project:
  id: ""
```