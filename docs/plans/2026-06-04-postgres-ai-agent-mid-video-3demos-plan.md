# Postgres AI Agent Mid-Video · 3 套 Remotion 预览 Demo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `features/content-pipeline/postgres-ai-agent-default-db-mid-video/` 下产出 `remotion-a/` `remotion-b/` `remotion-c/` 三个独立 Remotion 项目，各自 10 个真实 Scene 覆盖完整 SRT，可分别 `npm run dev` 预览（静默，不渲染）。

**Architecture:** 共用 `scene-boundaries.md`（按 SRT 实测时间锚定 10 段，总 479.20s），三套独立 `cli.mjs init` 脚手架；三套配色/typography 各自覆盖；三套 `audioConfig.ts` 帧数相同但 SCENES title/audioFile 字段一致；30 个 Scene 由 `skills/remotion-pipelines/workflows/gen-scenes.workflow.mjs` 三次调用并行生成；不挂 `<Audio>`，预览静默。

**Tech Stack:** Remotion 4 + React 18 + TypeScript 5；动画用 Remotion interpolate/spring 为主，复杂图形用 `shared/svg` 三件套 + Anime.js 4.4.1 备选；workflow 用 Workflow tool 调用 `gen-scenes.workflow.mjs`。

**Design source:** `docs/plans/2026-06-04-postgres-ai-agent-mid-video-3demos-design.md`

---

## 关键路径与并行机会

```
Task 1 (scene-boundaries.md)
   │
   ├── Task 2 (init remotion-a)  ──┐
   ├── Task 3 (init remotion-b)  ──┼── 三个 init 可并行
   └── Task 4 (init remotion-c)  ──┘
                                   │
   ┌──────── 三套 token 覆盖 ─────┴───────┐
   │ Task 5 (A token) │ Task 6 (B token) │ Task 7 (C token) │  ← 可并行
   └──────────────────────────────────────┘
                                   │
   ┌──────── 三套 audioConfig ────────────┐
   │ Task 8 (A) │ Task 9 (B) │ Task 10 (C) │  ← 可并行（内容几乎一致）
   └──────────────────────────────────────┘
                                   │
   ┌──────── 三套 gen-scenes workflow ────┐
   │ Task 11 (A) │ Task 12 (B) │ Task 13 (C) │ ← 可顺序/可并行
   └──────────────────────────────────────┘
                                   │
   ┌──────── 三套 dev 验证 ───────────────┐
   │ Task 14 (A) │ Task 15 (B) │ Task 16 (C) │
   └──────────────────────────────────────┘
```

---

## Task 1: 写公共底料 `scene-boundaries.md`

**Files:**
- Create: `features/content-pipeline/postgres-ai-agent-default-db-mid-video/production/timing/scene-boundaries.md`

**Step 1: 写文件内容**

完整内容（按 design §2 表 + scene-boundaries.template.md 模板）：

```markdown
# 场景翻页边界（Remotion · SRT 锚点对齐）

**音频真源**：`media/voiceover.wav`（待补）+ `subtitles/sub.srt`（已就绪 220 条）
**规则**：翻页落在 SRT **话题切换**句起点（过渡语「好的」「明白了」「对」仍属上一段）。
**总时长**：479.17s（14375 帧 ÷ 30fps）= SRT 末帧 7:59.20 - 33ms ✓
**FPS**：30

| 页 | id | Scene 组件 | 进入 (s) | 终 (s) | 时长 (s) | 帧 | 锚点 SRT# | 话题 | 下段切换号 |
|----|----|-----------|---------|--------|---------|----|----------|------|-----------|
| 1 | 01 | SceneCover | 0.000 | 12.780 | 12.78 | 383 | 1-4 | 封面：AI 时代 Postgres 怎么成默认 | 5 "我们先来说说PostgreSQL在AI应用" |
| 2 | 02 | ScenePhenomenon | 12.780 | 82.720 | 69.94 | 2098 | 5-35 | 现象：Agent 推荐 + 生态推动 + 反例小插曲 | 36 "好的 为什么模型会这么偏爱sql" |
| 3 | 03 | SceneCorpusJsonb | 82.720 | 142.800 | 60.08 | 1802 | 36-63 | SQL 训练语料占比 + DDL 可执行 + JSONB | 64 "原来postgres还有这么多优点 那postgres它是怎么能够在同一个实例里面" |
| 4 | 04 | SceneOneDb | 142.800 | 185.280 | 42.48 | 1274 | 64-79 | OLTP + LangGraph PostgresSaver 同库 | 80 "是的" + 81 "而且如果你要用rag架构的话" |
| 5 | 05 | ScenePgvector | 185.280 | 210.960 | 25.68 | 770 | 80-90 | pgvector 同库起步 | 91 "说到这我有个问题" |
| 6 | 06 | SceneSupply | 210.960 | 260.540 | 49.58 | 1487 | 91-113 | Supabase/Neon/RDS + Prisma/Drizzle + Cookbook | 114 "那我们下面要讨论的是 postgres和专用的向量库" |
| 7 | 07 | SceneVsDedicated | 260.540 | 323.860 | 63.32 | 1900 | 114-142 | pgvector vs 专用库 + Firecrawl 回归 | 143 "那有没有哪些场景是postgres作为默认的数据库 其实是不合适的" |
| 8 | 08 | SceneAntiCases | 323.860 | 389.480 | 65.62 | 1969 | 143-174 | SQLite/Mongo/两库/serverless + 上云背景收束 | 175 "我们再来谈谈开发者在做数据库决策的时候" |
| 9 | 09 | SceneChecklist | 389.480 | 446.880 | 57.40 | 1722 | 175-203 | 五条决策清单 | 204 "那我们最后再总结一下" |
| 10 | 10 | SceneOutro | 446.880 | 479.200 | 32.32 | 970 | 204-220 | 抄作业生态 + 收尾 | (SRT 末) |

**帧合计**：383+2098+1802+1274+770+1487+1900+1969+1722+970 = 14375 帧 = 479.17s（与 SRT 末帧 479.20s 差 33ms = 1 帧，可忽略）

## 关键归属决策

- **s02 末段 25-35（"反例小插曲"）**：归 s02 末，作"压倒性首选"收束（真正反例分析在 s08）。
- **s08 末段 170-174（"默认有前提 + 上云背景"）**：归 s08 末，作反例段收束尾。

## 三套视觉路线（详见 design §3）

- **方案 A**（remotion-a/）：多隐喻分布式，每场专属 SVG + aura
- **方案 B**（remotion-b/）：三幕克制叙事，5 套模板复用 + typography 主导
- **方案 C**（remotion-c/）：Postgres 实例为主角，一个核心组件 phase 推进
```

**Step 2: Commit**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/production/timing/scene-boundaries.md
git commit -m "feat(postgres-ai-agent): 写场景边界表（10 段，按 SRT 实测时间）"
```

---

## Task 2: 初始化 `remotion-a/` 脚手架

**Files:**
- Run: `node skills/remotion-pipelines/cli.mjs init features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/`
- Create: `features/.../postgres-ai-agent-default-db-mid-video/remotion-a/` (整套)

**Step 1: 跑 init**

```bash
cd /Users/superno/Documents/code/creative/one-context
node skills/remotion-pipelines/cli.mjs init features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/
```

Expected: 输出 "Initialized Remotion project at .../remotion-a/"，目录含 package.json、src/、scripts/、public/。

**Step 2: 验证 package.json 已注入跨平台 compositor**

```bash
grep "compositor-darwin-arm64" features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/package.json
```

Expected: 命中（macOS arm64）。

**Step 3: 改 package.json 项目名**

读 `remotion-a/package.json`，将 `"name"` 字段改为 `"postgres-ai-agent-remotion-a"`。

**Step 4: 跑 npm install**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a
npm install
```

Expected: 安装成功，无 ERR 关键字。可能 1-3 分钟。

**Step 5: 验证 dev 命令可启动（不实际启动）**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a
npx remotion versions
```

Expected: 输出 Remotion 版本号。

**Step 6: Commit**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/package.json features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/.gitignore features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/src features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/scripts features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/tsconfig.json features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/remotion.config.ts features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/public 2>/dev/null
git commit -m "feat(postgres-ai-agent): init remotion-a 脚手架"
```

---

## Task 3: 初始化 `remotion-b/` 脚手架

**Files:**
- Run: `node skills/remotion-pipelines/cli.mjs init features/.../remotion-b/`

**Step 1-6**：与 Task 2 完全相同，但路径 `remotion-a` → `remotion-b`，项目名 `postgres-ai-agent-remotion-b`。

**Step 6: Commit**

```bash
git commit -m "feat(postgres-ai-agent): init remotion-b 脚手架"
```

---

## Task 4: 初始化 `remotion-c/` 脚手架

**Files:**
- Run: `node skills/remotion-pipelines/cli.mjs init features/.../remotion-c/`

**Step 1-6**：与 Task 2 完全相同，但路径 `remotion-a` → `remotion-c`，项目名 `postgres-ai-agent-remotion-c`。

**Step 6: Commit**

```bash
git commit -m "feat(postgres-ai-agent): init remotion-c 脚手架"
```

---

## Task 5: 方案 A 配色 token + typography

**Files:**
- Modify: `features/.../remotion-a/src/shared/colors.ts`
- Modify: `features/.../remotion-a/src/shared/typography.ts`（确认 FONT_SIZE 表）

**Step 1: 改 `remotion-a/src/shared/colors.ts`**

完整 COLORS：

```typescript
export const COLORS = {
  bg: "#0a0a0b",
  text: "#f1efea",
  muted: "#a8a8a8",
  // 方案 A · 多隐喻分布式 · Postgres 品牌色家族
  accent: "#4f9ad6",         // PG 蓝
  accentDim: "rgba(79, 154, 214, 0.20)",
  accentLit: "rgba(79, 154, 214, 0.06)",
  accentWarm: "#f0a868",     // 生态金
  accentWarmDim: "rgba(240, 168, 104, 0.20)",
  // 辩论光谱色（s07 vs 专用库、s08 反例边界用）
  debateFast: "#6ec87a",     // 同库快派绿
  debateMiddle: "#e8a090",   // 中间派
  debateSlow: "#a585f0",     // 专用慢派紫
  // 图表辅助
  graphGrid: "rgba(241,239,234,0.06)",
  graphLine: "rgba(79, 154, 214, 0.4)",
} as const;
```

**Step 2: 确认 `remotion-a/src/shared/typography.ts` 字号符合方案 A**

读文件确认 `FONT_SIZE` 包含至少：`title: 140`、`subtitle: 60`、`cardTitle: 52`、`body: 44`、`svgText: 32`、`svgTextLarge: 40`、`coverTitle: 140`。

如缺，补齐对应字段。

**Step 3: Commit**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/src/shared/
git commit -m "feat(postgres-ai-agent-a): 配色 token = PG 蓝 + 生态金 + 辩论三色"
```

---

## Task 6: 方案 B 配色 token + typography

**Files:**
- Modify: `features/.../remotion-b/src/shared/colors.ts`
- Modify: `features/.../remotion-b/src/shared/typography.ts`

**Step 1: 改 `remotion-b/src/shared/colors.ts`**

```typescript
export const COLORS = {
  bg: "#0a0a0b",
  text: "#f1efea",
  muted: "#a8a8a8",
  // 方案 B · 三幕克制 · 暖灰极简
  accent: "#e8a090",         // 红铜
  accentDim: "rgba(232, 160, 144, 0.20)",
  accentLit: "rgba(232, 160, 144, 0.05)",
  // 三幕色（场景按所属幕引用）
  actI: "#6ea8d8",           // 幕 I 冷蓝（s01-s03）
  actIDim: "rgba(110, 168, 216, 0.18)",
  actII: "#e0b87a",          // 幕 II 暖金（s04-s07）
  actIIDim: "rgba(224, 184, 122, 0.18)",
  actIII: "#a585f0",         // 幕 III 紫罗兰（s08-s10）
  actIIIDim: "rgba(165, 133, 240, 0.18)",
  graphGrid: "rgba(241,239,234,0.06)",
  graphLine: "rgba(232,160,144,0.4)",
} as const;
```

**Step 2: 确认 typography 字号支持方案 B 的"标题大"特征**

读 `remotion-b/src/shared/typography.ts`，确认 `FONT_SIZE.title: 160`、`body: 48`。如缺补齐。

**Step 3: Commit**

```bash
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-b/src/shared/
git commit -m "feat(postgres-ai-agent-b): 配色 token = 三幕渐变（蓝/金/紫）"
```

---

## Task 7: 方案 C 配色 token + typography

**Files:**
- Modify: `features/.../remotion-c/src/shared/colors.ts`
- Modify: `features/.../remotion-c/src/shared/typography.ts`

**Step 1: 改 `remotion-c/src/shared/colors.ts`**

```typescript
export const COLORS = {
  bg: "#0a0a0b",
  text: "#f1efea",
  muted: "#a8a8a8",
  // 方案 C · 实例为主角 · Postgres 品牌深蓝
  accent: "#336791",         // Postgres 深蓝
  accentDim: "rgba(51, 103, 145, 0.20)",
  accentLit: "rgba(51, 103, 145, 0.05)",
  accentBright: "#5a9bd4",   // 高亮当前生长层
  accentBrightDim: "rgba(90, 155, 212, 0.25)",
  // 大象色（吉祥物水印 + s10 收尾时浮现）
  elephant: "rgba(241, 239, 234, 0.08)",
  graphGrid: "rgba(241,239,234,0.06)",
  graphLine: "rgba(51, 103, 145, 0.4)",
} as const;
```

**Step 2: 确认 typography 字号符合方案 C 的"主视觉为主、文字克制"**

读 `remotion-c/src/shared/typography.ts`，确认 `FONT_SIZE.title: 130`、`body: 44`。如缺补齐。

**Step 3: Commit**

```bash
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-c/src/shared/
git commit -m "feat(postgres-ai-agent-c): 配色 token = Postgres 深蓝 + 大象色"
```

---

## Task 8: 方案 A `audioConfig.ts`

**Files:**
- Modify: `features/.../remotion-a/src/audioConfig.ts`

**Step 1: 写完整 audioConfig.ts**

```typescript
// audioConfig.ts — Postgres AI Agent 中视频 · 方案 A
// 时长真源：production/timing/scene-boundaries.md（按 SRT 实测时间锚定）
// 静默预览：audioFile 保留为约定路径，Composition 暂不挂 <Audio>

export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

export const FPS = 30;

export const SCENES: SceneConfig[] = [
  { id: "01", title: "封面：AI 时代 Postgres 怎么成默认",        durationInFrames: 383,  audioFile: "audio/voiceover.wav" },
  { id: "02", title: "现象：Agent 推荐 + 生态推动 + 反例小插曲", durationInFrames: 2098, audioFile: "audio/voiceover.wav" },
  { id: "03", title: "SQL 训练语料 + DDL 可执行 + JSONB",       durationInFrames: 1802, audioFile: "audio/voiceover.wav" },
  { id: "04", title: "OLTP + LangGraph PostgresSaver 同库",     durationInFrames: 1274, audioFile: "audio/voiceover.wav" },
  { id: "05", title: "pgvector 同库起步",                       durationInFrames: 770,  audioFile: "audio/voiceover.wav" },
  { id: "06", title: "Supabase/Neon/RDS + 框架供应链",          durationInFrames: 1487, audioFile: "audio/voiceover.wav" },
  { id: "07", title: "pgvector vs 专用库 + Firecrawl 回归",     durationInFrames: 1900, audioFile: "audio/voiceover.wav" },
  { id: "08", title: "SQLite/Mongo/两库/serverless + 上云",     durationInFrames: 1969, audioFile: "audio/voiceover.wav" },
  { id: "09", title: "五条决策清单",                            durationInFrames: 1722, audioFile: "audio/voiceover.wav" },
  { id: "10", title: "抄作业生态 + 收尾",                       durationInFrames: 970,  audioFile: "audio/voiceover.wav" },
];

export function getSceneStart(sceneIndex: number): number {
  let start = 0;
  for (let i = 0; i < sceneIndex; i++) start += SCENES[i].durationInFrames;
  return start;
}

export const TOTAL_FRAMES = SCENES.reduce((sum, s) => sum + s.durationInFrames, 0);
```

**Step 2: 验证总帧数**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a
node -e "import('./src/audioConfig.ts').then(m => console.log('TOTAL_FRAMES:', m.TOTAL_FRAMES))" 2>&1 | tail -3
```

如 node 不支持直接 import ts，可用 grep 求和验证：

```bash
grep -oE "durationInFrames: [0-9]+" src/audioConfig.ts | awk -F': ' '{s+=$2} END {print "sum:", s}'
```

Expected: `sum: 14375`

**Step 3: Commit**

```bash
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/src/audioConfig.ts
git commit -m "feat(postgres-ai-agent-a): audioConfig.ts 10 场 14375 帧"
```

---

## Task 9: 方案 B `audioConfig.ts`

**Files:**
- Modify: `features/.../remotion-b/src/audioConfig.ts`

**Step 1-3**：与 Task 8 完全相同（audioConfig 内容与方案无关），只是路径 `remotion-a` → `remotion-b`。

**Step 3: Commit**

```bash
git commit -m "feat(postgres-ai-agent-b): audioConfig.ts 10 场 14375 帧"
```

---

## Task 10: 方案 C `audioConfig.ts`

**Files:**
- Modify: `features/.../remotion-c/src/audioConfig.ts`

**Step 1-3**：与 Task 8 完全相同，只是路径 `remotion-a` → `remotion-c`。

**Step 3: Commit**

```bash
git commit -m "feat(postgres-ai-agent-c): audioConfig.ts 10 场 14375 帧"
```

---

## Task 11: 方案 A 用 `gen-scenes` workflow 批量生成 10 个 Scene

**Files:**
- Create: `features/.../remotion-a/src/scenes/Scene01Cover.tsx` ~ `Scene10Outro.tsx`
- Create: `features/.../remotion-a/src/scenes/svg/*.tsx`（约 10-12 个隐喻组件）
- Modify: `features/.../remotion-a/src/scenes/index.tsx`（SceneRouter）

**Step 1: 触发 gen-scenes workflow**

调用 Workflow tool（用户在本任务执行时必须**显式输入 "workflow"** 或这是 workflow 触发上下文）：

```javascript
Workflow({
  scriptPath: "/Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines/workflows/gen-scenes.workflow.mjs",
  args: {
    featureDir: "/Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a",
    srtPath:    "/Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/production/subtitles/sub.srt",
    boundariesPath: "/Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/production/timing/scene-boundaries.md",
    sharedDir:  "/Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/src/shared",
    skillDir:   "/Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines",
    styleGuide: "方案 A · 多隐喻分布式：每场专属 SVG 隐喻 + 专属 aura；色彩 = PG 蓝/生态金/辩论三色（debateFast/Middle/Slow）；字号 = 标题 140/正文 44/SVG text 32-40；隐喻清单：s01 ConcentricLayers / s02 PromptFlowRiver / s03 CorpusBarChart+JsonbPills / s04 LayeredInstance+DataFlowArrows / s05 ExtensionBadge / s06 SupplyFunnel / s07 SplitVerdict+TimelineMigration / s08 BoundarySpectrum / s09 ChecklistCards / s10 CopyPaperStack。注意：每场必须有前景大视觉，封面 ≥120px 主标题；不挂 <Audio>（静默预览）。"
  }
})
```

**Step 2: 等待 workflow 完成**

workflow 完成后会返回每场 audit 结果。如果有 blocker，记录场号准备后续重写。

**Step 3: 应用 workflow 输出**

workflow 返回每个 Scene 的 `{filename, code, routerCase}`，主线 agent 应：
1. 写入对应 tsx 文件
2. 更新 `src/scenes/index.tsx` 的 SceneRouter switch

**Step 4: 跑 TypeScript 类型检查**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a
npx tsc --noEmit
```

Expected: 无类型错误。如有，记录并修复（不重跑 workflow）。

**Step 5: Commit**

```bash
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a/src/scenes/
git commit -m "feat(postgres-ai-agent-a): 生成 10 场 Scene + svg 隐喻组件"
```

**Notes:**
- 若 workflow 调用失败或 audit 多场 blocker，**降级**：主线 agent 用 Agent tool 并行 dispatch 10 个 subagent，每个 subagent 写一个 Scene；subagent prompt 含该场 SRT 切片 + 隐喻名 + design §3 配色字号约束
- workflow 触发条件需用户显式输入 "workflow"——执行此 task 前先确认

---

## Task 12: 方案 B 用 `gen-scenes` workflow 批量生成 10 个 Scene

**Files:**
- 同 Task 11，路径换 `remotion-b`

**Step 1: 触发 workflow**

```javascript
Workflow({
  scriptPath: "...同上...",
  args: {
    featureDir: "..../remotion-b",
    srtPath:    "...同上...",
    boundariesPath: "...同上...",
    sharedDir:  "..../remotion-b/src/shared",
    skillDir:   "...同上...",
    styleGuide: "方案 B · 三幕克制叙事：5 套通用模板复用（PhenomenonFlow / StackedLayers / SideBySide / SpectrumGrid / NumberedCards），按场景内容换填核心数据/标签避免同质化；色彩 = 红铜 + 三幕渐变（actI 冷蓝 s01-s03 / actII 暖金 s04-s07 / actIII 紫罗兰 s08-s10）；字号 = 标题 160/正文 48（更大字幕主导）；同幕内场景背景一致，靠 typography 与配色而非每场新图形撑表现力。各场模板映射：s01 NumberedCards-变体 / s02 PhenomenonFlow / s03 StackedLayers(SQL+JSONB 两层) / s04 StackedLayers(OLTP+Checkpoint+Vector 三层) / s05 SideBySide(pgvector vs 早期纠结) / s06 PhenomenonFlow(供应链版) / s07 SideBySide(Postgres vs Pinecone) / s08 SpectrumGrid(适用边界) / s09 NumberedCards(5 条) / s10 NumberedCards-收尾变体。"
  }
})
```

**Step 2-5**: 同 Task 11。

**Commit message:**

```bash
git commit -m "feat(postgres-ai-agent-b): 生成 10 场 Scene + 5 通用模板复用"
```

---

## Task 13: 方案 C 用 `gen-scenes` workflow 批量生成 10 个 Scene

**Files:**
- 同 Task 11，路径换 `remotion-c`

**Step 1: 触发 workflow**

```javascript
Workflow({
  scriptPath: "...同上...",
  args: {
    featureDir: "..../remotion-c",
    srtPath:    "...同上...",
    boundariesPath: "...同上...",
    sharedDir:  "..../remotion-c/src/shared",
    skillDir:   "...同上...",
    styleGuide: "方案 C · Postgres 实例为主角：全片同一片机房深空背景 + 大象 logo 水印；前景始终是同一个 PostgresInstanceCanvas 组件渐进生长，受控参数 phase（1-10）决定显示哪些层/扩展/外壳/对手。色彩 = Postgres 深蓝 #336791 + accentBright 高亮当前层；实例占画布 60%+，文字克制（标题 130/旁白卡 44）。各场 phase 映射：s01(phase=1, 单实例诞生) / s02(phase=2, 多 Agent 箭头汇聚) / s03(phase=3, JSONB 凸起 + 训练数据云) / s04(phase=4, 长出 LangGraph 检查点表) / s05(phase=5, 长出 pgvector 扩展徽章) / s06(phase=6, 套上 Supabase/Neon 外壳) / s07(phase=7, 右侧出现 Pinecone 对手 + Firecrawl 回归箭头) / s08(phase=8, SQLite/Mongo 飘走 + 上云背景) / s09(phase=9, 实例缩到右下角，左侧出 5 条决策清单) / s10(phase=10, 实例放大居中 + 抄作业代码片段堆叠环绕)。共享核心组件：PostgresInstanceCanvas 放 src/scenes/svg/，每个 SceneXxx 主要逻辑 = 设 phase + OverlayText 旁白卡。"
  }
})
```

**Step 2-5**: 同 Task 11。

**Commit message:**

```bash
git commit -m "feat(postgres-ai-agent-c): 生成 10 场 Scene + PostgresInstanceCanvas 主角"
```

---

## Task 14: 方案 A `npm run dev` 预览验证

**Files:**
- 无修改，只验证

**Step 1: 启动 dev server**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/postgres-ai-agent-default-db-mid-video/remotion-a
npm run dev
```

Expected: Remotion Studio 启动在 http://localhost:3000；终端无 ERROR。

**Step 2: 用户在浏览器打开 Studio，按以下清单肉眼检查**

- [ ] 侧边栏有 composition（名称形如 SlideVideo 或 PostgresAIAgent）
- [ ] 总时长显示 ≈ 7:59（14375 帧 ÷ 30fps，与 SRT 末帧差 33ms 可忽略）
- [ ] 拖到 s01 中间帧（约 0:06）：封面有大视觉（≥120px 主标题、SVG 占画布 50%+）
- [ ] 拖到 s04 中间帧（约 2:44）：OLTP + 检查点同库视觉清晰，分层架构图含数据流箭头
- [ ] 拖到 s07 中间帧（约 4:52）：左右对比（pgvector vs 专用库）+ Firecrawl 时间轴
- [ ] 拖到 s09 中间帧（约 7:00）：5 条决策卡片可见
- [ ] 全片无运行时 console error

**Step 3: 关闭 dev server，记录任何 blocker**

如有 blocker，列在 `features/.../review_record.md` 等水猿挑出需重写的场景。

**Step 4: Commit verify 记录**（如有）

```bash
git add features/content-pipeline/postgres-ai-agent-default-db-mid-video/review_record.md
git commit -m "test(postgres-ai-agent-a): 预览验证 + 待修清单"
```

---

## Task 15: 方案 B `npm run dev` 预览验证

**Files:**
- 无修改，只验证

**Step 1-4**: 与 Task 14 相同，路径换 `remotion-b`。

肉眼检查清单调整：
- [ ] 拖到 s02 中间帧：PhenomenonFlow 模板填充"Agent 推荐 + 生态推动"内容，非空模板
- [ ] 拖到 s03/s04 中间帧：StackedLayers 两/三层数据不同（s03 = SQL+JSONB，s04 = OLTP+Checkpoint+Vector）
- [ ] 三幕背景色不同（s01-s03 冷蓝、s04-s07 暖金、s08-s10 紫罗兰）
- [ ] 标题字号显著大于方案 A（≥160px）

---

## Task 16: 方案 C `npm run dev` 预览验证

**Files:**
- 无修改，只验证

**Step 1-4**: 与 Task 14 相同，路径换 `remotion-c`。

肉眼检查清单调整：
- [ ] 拖到 s01 → s05 → s10 三帧：PostgresInstanceCanvas 的 phase 渐进可见（从单实例 → pgvector 扩展 → 抄作业生态）
- [ ] s09 验证：实例缩到右下角不抢戏，5 条决策清单在左侧可读
- [ ] 全片背景一致（机房深空 + 大象水印）
- [ ] 主视觉始终占画布 60%+

---

## 全部完成后

**Step: 汇总三套对比**

主线 agent 在 `features/.../review_record.md` 写一段 brief：

```markdown
# 三套 demo 预览对比（2026-06-04）

| 维度 | A 多隐喻 | B 三幕克制 | C 实例为主 |
|---|---|---|---|
| 表现力 | | | |
| 一致性 | | | |
| 抓眼程度 | | | |
| 后续改造空间 | | | |
| blocker 数 | | | |
```

由水猿挑出主推方案后，进入下一阶段（render + burn-subtitles + cover），本计划完成。

---

## 风险与降级

| 风险 | 信号 | 降级 |
|---|---|---|
| workflow 触发受限（用户未输入 "workflow"） | Workflow tool 拒绝调用 | 改用 10 个 Agent tool 并行 dispatch，每 subagent 写一个 Scene |
| init 后 npm install 失败（如代理） | npm ERR / network | 设 `HTTPS_PROXY=http://127.0.0.1:13659` 重试 |
| compositor 包未匹配本机平台 | dev 启动报"Could not find compositor binary" | 手动 `npm i @remotion/compositor-darwin-arm64`（按 SKILL.md 跨平台表） |
| Scene 一轮生成质量不齐 | audit blocker ≥3 | 接受；记录到 review_record.md，水猿挑后定向重写 |
| 三套独立 node_modules 占空间 ≈ 1.5GB | 磁盘告警 | 接受；预览看完水猿挑定主推方案后可 rm 另两套 |
| audioConfig 与 scene-boundaries 不同步 | 总帧 ≠ 14375 | 必须重对账，单一数据源 = scene-boundaries.md §2 表 |
