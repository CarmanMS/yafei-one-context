# 腾讯超级团队 Remotion 演示 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 tencent-super-team-mid-video 生成三版 Remotion 项目（Cyber/Biz/Sk），9 场景 × 3 风格 = 27 个场景组件，仅预览不渲染。

**Architecture:** 三套独立 Remotion 项目通过 `cli.mjs init` 初始化，共享 `production/` 音频/字幕/时序数据。每个项目有独立 `style-guide.ts` 视觉宪法，场景组件严格引用 style-guide 获取颜色/字体/间距/动画参数。按 S0→S8 逐场景推进，每场景三版同步完成。

**Tech Stack:** Remotion 4.x, React 18, TypeScript, Anime.js 4.x, GSAP 3.x, Lottie (Sketch 风格), 现有 shared/ 组件库

---

## Task 1: 初始化三个 Remotion 项目

**Files:**
- Create: `features/content-pipeline/tencent-super-team-mid-video/remotion-cyber/` （整个目录）
- Create: `features/content-pipeline/tencent-super-team-mid-video/remotion-biz/` （整个目录）
- Create: `features/content-pipeline/tencent-super-team-mid-video/remotion-sketch/` （整个目录）

**Step 1: 初始化 Cyber 项目**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
node cli.mjs init /Users/superno/Documents/code/creative/one-context/features/content-pipeline/tencent-super-team-mid-video/remotion-cyber
```

Expected: 项目创建成功，`remotion-cyber/` 下出现 `package.json`, `src/`, `scripts/`, `public/audio/`

**Step 2: 初始化 Biz 项目**

```bash
node cli.mjs init /Users/superno/Documents/code/creative/one-context/features/content-pipeline/tencent-super-team-mid-video/remotion-biz
```

**Step 3: 初始化 Sketch 项目**

```bash
node cli.mjs init /Users/superno/Documents/code/creative/one-context/features/content-pipeline/tencent-super-team-mid-video/remotion-sketch
```

**Step 4: 安装依赖**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npm install
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/tencent-super-team-mid-video/remotion-biz && npm install
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/tencent-super-team-mid-video/remotion-sketch && npm install
```

**Step 5: 提交初始化**

```bash
cd /Users/superno/Documents/code/creative/one-context
git add features/content-pipeline/tencent-super-team-mid-video/remotion-cyber/ remotion-biz/ remotion-sketch/
git commit -m "feat(tencent-super-team): init three remotion projects (cyber/biz/sketch)"
```

---

## Task 2: 配置 audioConfig.ts（三套项目共用时序数据）

**Files:**
- Modify: `remotion-cyber/src/audioConfig.ts`
- Modify: `remotion-biz/src/audioConfig.ts`
- Modify: `remotion-sketch/src/audioConfig.ts`

**Step 1: 写入 audioConfig.ts**

三个项目使用相同的 audioConfig 内容（策略 A：single 模式，完整 WAV）。音频文件通过相对路径引用 `../production/media/voiceover.wav`。

```typescript
// audioConfig.ts — 腾讯超级团队中视频
// 场景数据源: production/timing/scene-boundaries.md + wav-durations.json
// 策略 A：完整 WAV，时长由 scene-boundaries 锚定

export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

const FPS = 30;
const AUDIO_FILE = "audio/voiceover.wav";

// 场景时长来自 wav-durations.json: [14.56, 123.64, 52.78, 103.88, 53.28, 66.52, 111.8, 51.82, 137.37]
const DURATIONS = [14.56, 123.64, 52.78, 103.88, 53.28, 66.52, 111.8, 51.82, 137.37];
const TITLES = ["封面", "AI采用鸿沟", "演化链", "四特征", "觉醒路径", "为何需要团队", "三种形态", "案例", "园丁收束"];

export const SCENES: SceneConfig[] = DURATIONS.map((dur, i) => ({
  id: `s${i}`,
  title: TITLES[i],
  durationInFrames: Math.round(dur * FPS),
  audioFile: AUDIO_FILE,
}));

export function getSceneStart(sceneIndex: number): number {
  return SCENES.slice(0, sceneIndex).reduce((sum, s) => sum + s.durationInFrames, 0);
}

export const TOTAL_FRAMES = SCENES.reduce((sum, s) => sum + s.durationInFrames, 0);
export { FPS };
```

**Step 2: 复制 WAV 到 public/audio/**

```bash
# 确保源音频存在
ls features/content-pipeline/tencent-super-team-mid-video/production/media/voiceover.wav

# 复制到三个项目的 public/audio/
cp features/content-pipeline/tencent-super-team-mid-video/production/media/voiceover.wav features/content-pipeline/tencent-super-team-mid-video/remotion-cyber/public/audio/
cp features/content-pipeline/tencent-super-team-mid-video/production/media/voiceover.wav features/content-pipeline/tencent-super-team-mid-video/remotion-biz/public/audio/
cp features/content-pipeline/tencent-super-team-mid-video/production/media/voiceover.wav features/content-pipeline/tencent-super-team-mid-video/remotion-sketch/public/audio/
```

Expected: 三个 `public/audio/voiceover.wav` 就位，Remotion `staticFile("audio/voiceover.wav")` 可正确引用

**Step 3: 更新 scenes/index.tsx 路由**

三个项目的 `src/scenes/index.tsx` 都更新 SceneRouter，添加 9 个 case（初始指向占位组件）：

```tsx
function SceneRouter({ id, index }: { id: string; index: number }) {
  switch (id) {
    case "s0": return <SceneCover />;
    case "s1": return <SceneGap />;
    case "s2": return <SceneEvolution />;
    case "s3": return <SceneFourTraits />;
    case "s4": return <SceneAwaken />;
    case "s5": return <SceneWhyTeam />;
    case "s6": return <SceneForms />;
    case "s7": return <SceneCases />;
    case "s8": return <SceneGardener />;
    default: return <PlaceholderScene index={index} />;
  }
}
```

各 import 暂指向占位组件（返回标题+编号的简单组件），后续 Task 逐步替换。

**Step 4: 验证 Remotion Studio**

```bash
cd features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npm run dev
```

Expected: 浏览器打开后看到 9 个占位场景，音频播放正常，总时长约 715.6s

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(tencent-super-team): configure audioConfig + scene routing for all 3 projects"
```

---

## Task 3: 创建 style-guide.ts（三套视觉宪法）

**Files:**
- Create: `remotion-cyber/src/style-guide.ts`
- Create: `remotion-biz/src/style-guide.ts`
- Create: `remotion-sketch/src/style-guide.ts`

**Step 1: Cyber style-guide.ts**

```typescript
// remotion-cyber/src/style-guide.ts
// 科技简约 + 数据可视化 风格

export const theme = {
  name: "cyber" as const,

  colors: {
    primary: "#00f5d4",       // 霓虹青
    secondary: "#b388ff",     // 强调紫
    accent: "#ff4757",        // 警示红
    warning: "#ffa502",       // 橙色告警
    bg: "#0a0a1a",            // 深色背景
    bgSecondary: "#1a1a3a",   // 次级背景
    text: "#f1efea",          // 主文本
    textMuted: "#a8a8a8",     // 次要文本
    glow: "rgba(0,245,212,0.3)",   // 霓虹发光
    glowSecondary: "rgba(179,136,255,0.3)",
    graphGrid: "rgba(241,239,234,0.06)",
    graphLine: "rgba(0,245,212,0.4)",
    cardBg: "rgba(26,26,58,0.7)",
    cardBorder: "rgba(0,245,212,0.3)",
  },

  typography: {
    heading: '"Space Grotesk", "Noto Sans SC", sans-serif',
    body: '"Inter", "Noto Sans SC", sans-serif',
    caption: '"Inter", "Noto Sans SC", sans-serif',
    mono: '"JetBrains Mono", monospace',
    display: '"Space Grotesk", sans-serif',
  },

  spacing: {
    xs: 8,
    sm: 16,
    md: 32,
    lg: 48,
    xl: 72,
    section: 96,
  },

  shapes: {
    cardRadius: 4,
    cardBorder: "1px solid rgba(0,245,212,0.3)",
    cardShadow: "0 0 20px rgba(0,245,212,0.15)",
    cardBg: "rgba(26,26,58,0.7)",
    cardBackdrop: "blur(12px)",
  },

  animations: {
    transitionDuration: 0.6,    // 秒
    stagger: 80,                // 毫秒
    easing: "outExpo" as const,
    glow: true,
    pulse: true,
    particleColor: "#00f5d4",
    dataFlowColor: "#b388ff",
  },

  backgrounds: {
    default: { type: "circuit" as const, intensity: 0.5 },
    emphasis: { type: "particles" as const, intensity: 0.7 },
    cover: { type: "custom" as const },  // 封面用专属背景
  },

  fontSizes: {
    display: 180,
    hero: 128,
    title: 84,
    subtitle: 56,
    body: 48,
    label: 40,
    mono: 36,
    caption: 32,
  },
} as const;

export type Theme = typeof theme;
```

**Step 2: Biz style-guide.ts**

```typescript
// remotion-biz/src/style-guide.ts
// 商务专业 + 图表驱动 风格

export const theme = {
  name: "biz" as const,

  colors: {
    primary: "#1e40af",       // 深蓝
    secondary: "#d97706",     // 金色
    accent: "#059669",        // 绿色（成功指标）
    warning: "#dc2626",       // 红色（警示）
    bg: "#f8fafc",            // 浅色背景
    bgSecondary: "#e2e8f0",   // 次级背景
    text: "#1e293b",          // 主文本深灰
    textMuted: "#64748b",     // 次要文本
    glow: "transparent",      // 商务风不用发光
    glowSecondary: "transparent",
    graphGrid: "rgba(30,64,175,0.08)",
    graphLine: "rgba(30,64,175,0.6)",
    cardBg: "#ffffff",
    cardBorder: "1px solid #e2e8f0",
  },

  typography: {
    heading: '"Source Serif 4", "Noto Serif SC", serif',
    body: '"Noto Sans SC", sans-serif',
    caption: '"Noto Sans SC", sans-serif',
    mono: '"JetBrains Mono", monospace',
    display: '"Source Serif 4", serif',
  },

  spacing: {
    xs: 8,
    sm: 16,
    md: 32,
    lg: 48,
    xl: 72,
    section: 96,
  },

  shapes: {
    cardRadius: 12,
    cardBorder: "1px solid #e2e8f0",
    cardShadow: "0 1px 3px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.08)",
    cardBg: "#ffffff",
    cardBackdrop: "none",
  },

  animations: {
    transitionDuration: 0.5,
    stagger: 100,
    easing: "outCubic" as const,
    glow: false,
    pulse: false,
    particleColor: "#1e40af",
    dataFlowColor: "#d97706",
  },

  backgrounds: {
    default: { type: "grid" as const, intensity: 0.3 },
    emphasis: { type: "gradient" as const, intensity: 0.5 },
    cover: { type: "custom" as const },
  },

  fontSizes: {
    display: 160,
    hero: 120,
    title: 84,
    subtitle: 56,
    body: 48,
    label: 40,
    mono: 36,
    caption: 32,
  },
} as const;

export type Theme = typeof theme;
```

**Step 3: Sketch style-guide.ts**

```typescript
// remotion-sketch/src/style-guide.ts
// 手绘/白板 风格

export const theme = {
  name: "sketch" as const,

  colors: {
    primary: "#2d3436",       // 深灰（主笔）
    secondary: "#0984e3",     // 蓝笔
    accent: "#d63031",        // 红笔
    warning: "#fdcb6e",       // 黄色高亮
    bg: "#fafafa",            // 白板底色
    bgSecondary: "#f0f0f0",   // 次级底色
    text: "#2d3436",          // 主文本
    textMuted: "#636e72",     // 次要文本
    glow: "transparent",
    glowSecondary: "transparent",
    graphGrid: "rgba(45,52,54,0.05)",
    graphLine: "rgba(9,132,227,0.5)",
    cardBg: "#fff9c4",        // 便利贴黄
    cardBorder: "2px dashed #636e72",
  },

  typography: {
    heading: '"Ma Shan Zheng", "Caveat", cursive',
    body: '"Caveat", "Ma Shan Zheng", cursive',
    caption: '"Caveat", cursive',
    mono: '"JetBrains Mono", monospace',
    display: '"Ma Shan Zheng", cursive',
  },

  spacing: {
    xs: 8,
    sm: 16,
    md: 32,
    lg: 48,
    xl: 72,
    section: 96,
  },

  shapes: {
    cardRadius: 2,            // 近直角，手绘感
    cardBorder: "2px dashed #636e72",
    cardShadow: "2px 3px 0px rgba(0,0,0,0.1)",
    cardBg: "#fff9c4",        // 便利贴黄
    cardBackdrop: "none",
  },

  animations: {
    transitionDuration: 0.4,
    stagger: 120,             // 手绘节奏更慢
    easing: "outBack" as const,
    glow: false,
    pulse: false,
    particleColor: "#0984e3",
    dataFlowColor: "#00b894",
  },

  backgrounds: {
    default: { type: "whiteboard" as const, intensity: 0.3 },
    emphasis: { type: "whiteboard" as const, intensity: 0.5 },
    cover: { type: "custom" as const },
  },

  fontSizes: {
    display: 160,
    hero: 120,
    title: 84,
    subtitle: 56,
    body: 48,
    label: 40,
    mono: 36,
    caption: 32,
  },
} as const;

export type Theme = typeof theme;
```

**Step 4: 在各项目的 scenes 组件中创建 useTheme hook**

每个项目创建 `src/hooks/useTheme.ts`：

```typescript
import { theme } from "../style-guide";
export { theme };
export type { Theme } from "../style-guide";
export const useTheme = () => theme;
```

**Step 5: 提交**

```bash
git add -A && git commit -m "feat(tencent-super-team): add style-guide.ts for cyber/biz/sketch themes"
```

---

## Task 4: 创建场景专用 SVG 组件目录和占位文件

**Files:**
- Create: `remotion-cyber/src/scenes/svg/` （场景专用 SVG 组件目录）
- Create: `remotion-biz/src/scenes/svg/`
- Create: `remotion-sketch/src/scenes/svg/`

**Step 1: 创建目录和 .gitkeep**

```bash
mkdir -p remotion-cyber/src/scenes/svg remotion-biz/src/scenes/svg remotion-sketch/src/scenes/svg
touch remotion-cyber/src/scenes/svg/.gitkeep remotion-biz/src/scenes/svg/.gitkeep remotion-sketch/src/scenes/svg/.gitkeep
```

**Step 2: 创建共享 SVG 动画 hooks**

SKILL.md 提到 `shared/svg/` 三件套（useStrokeReveal, useGrowIn, usePulse）但文件尚不存在。在 shared 层创建（三个项目 init 时自动复制）：

在 `skills/remotion-pipelines/src/shared/svg/` 下创建这三个 hook，然后在三个项目中手动复制。

```typescript
// shared/svg/useStrokeReveal.ts
import { interpolate } from "remotion";

/**
 * SVG 描线动画 — strokeDashoffset 从路径全长到 0。
 * 返回 strokeDasharray 和 strokeDashoffset 样式对象。
 */
export function useStrokeReveal(
  pathLength: number,
  startFrame: number,
  durationFrames: number,
  frame: number,
) {
  const progress = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return {
    strokeDasharray: pathLength,
    strokeDashoffset: pathLength * (1 - progress),
  };
}
```

```typescript
// shared/svg/useGrowIn.ts
import { interpolate, spring } from "remotion";

/**
 * 缩放弹入动画 — scale(0)→1 + opacity 0→1。
 */
export function useGrowIn(
  startFrame: number,
  fps: number,
  frame: number,
  config?: { damping?: number; stiffness?: number; mass?: number },
) {
  const entrance = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: config?.damping ?? 18, stiffness: config?.stiffness ?? 200, mass: config?.mass ?? 0.6 },
  });
  const scale = interpolate(entrance, [0, 1], [0, 1]);
  const opacity = interpolate(entrance, [0, 1], [0, 1]);
  return { transform: `scale(${scale})`, opacity };
}
```

```typescript
// shared/svg/usePulse.ts
import { interpolate } from "remotion";

/**
 * 呼吸脉冲动画 — opacity 和 scale 周期性变化。
 */
export function usePulse(
  startFrame: number,
  cycles: number,
  durationFrames: number,
  frame: number,
) {
  const progress = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, cycles * Math.PI * 2],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const pulse = Math.sin(progress) * 0.5 + 0.5;
  return {
    opacity: 0.5 + pulse * 0.5,
    transform: `scale(${0.95 + pulse * 0.1})`,
  };
}
```

```typescript
// shared/svg/index.ts
export { useStrokeReveal } from "./useStrokeReveal";
export { useGrowIn } from "./useGrowIn";
export { usePulse } from "./usePulse";
```

**Step 3: 同步到三个项目**

```bash
# 将 svg/ 目录复制到三个项目的 shared/
cp -r skills/remotion-pipelines/src/shared/svg/ remotion-cyber/src/shared/svg/
cp -r skills/remotion-pipelines/src/shared/svg/ remotion-biz/src/shared/svg/
cp -r skills/remotion-pipelines/src/shared/svg/ remotion-sketch/src/shared/svg/
```

**Step 4: 提交**

```bash
git add -A && git commit -m "feat(tencent-super-team): add SVG hooks + scenes/svg/ dirs for all 3 projects"
```

---

## Task 5: S0 封面 — 三版实现

**Files:**
- Create: `remotion-cyber/src/scenes/SceneCover.tsx`
- Create: `remotion-biz/src/scenes/SceneCover.tsx`
- Create: `remotion-sketch/src/scenes/SceneCover.tsx`
- Create: `remotion-cyber/src/scenes/svg/FormulaParticles.tsx` (Cyber 公式粒子)
- Create: `remotion-biz/src/scenes/svg/FormulaCards.tsx` (Biz 公式卡片)
- Create: `remotion-sketch/src/scenes/svg/HandDrawnFormula.tsx` (Sketch 手绘公式)

**视觉需求（来自设计文档）：**

- **Cyber**: 公式在矩阵雨中浮现，数据粒子汇成公式字符。GSAP 粒子汇聚 → 公式从模糊到清晰 → 标题 typewriter 出场
- **Biz**: 公式从底部逐行上升，如幻灯片演示。Remotion spring 入场 → 数字滚动到目标值 → 副标题 fade-in
- **Sketch**: 手写公式从左到右"写出"。strokeDashoffset 路径绘制 → 完成后墨迹扩散 → 标题手写体入场

**核心公式**: 组织竞争力 = 人才密度 × AI杠杆 / 组织摩擦

**Step 1: 实现 Cyber SceneCover**

437 帧（14.56s × 30fps）。入场动画前 2s，公式展示 8s，标题 4.56s。

关键实现要点：
- 背景：`<SceneBackground intensity={0.7} scanBeam />` 或封面专属矩阵雨背景
- 前景主视觉：公式 SVG 占画布 50%+，三个因子（人才密度、AI杠杆、组织摩擦）用 SVG 文字 + 发光效果
- 动画：GSAP `useGSAPTimeline` 编排粒子汇聚 → 公式淡入 → 数值高亮 → 标题 typewriter
- 标题字号 ≥120px（设计约束）
- 引用 `style-guide.ts` 的 `theme` 对象

**Step 2: 实现 Biz SceneCover**

- 背景：浅色渐变 + 微妙网格线
- 公式从底部 spring 入场，三行逐行出现
- 数字滚动计数动画（88% → 1% 等）
- 副标题 fade-in

**Step 3: 实现 Sketch SceneCover**

- 背景：白板质感 + 淡网格线
- `useStrokeReveal` 手写公式路径绘制
- 完成后墨迹扩散效果（opacity 波纹）
- 手写体标题入场

**Step 4: 更新三个项目的 scenes/index.tsx import 路径**

确保 `case "s0": return <SceneCover />` 指向实际组件而非占位。

**Step 5: 验证 Remotion Studio 预览**

```bash
cd remotion-cyber && npm run dev   # 分别检查三版
cd remotion-biz && npm run dev
cd remotion-sketch && npm run dev
```

检查清单：
- [ ] 封面前景主视觉占画布 ≥50%
- [ ] 标题字号 ≥120px
- [ ] 音频同步正常（14.56s 场景时长）
- [ ] 引用 style-guide.ts，无硬编码颜色
- [ ] 画布利用率 ≥70%

**Step 6: 提交**

```bash
git add -A && git commit -m "feat(tencent-super-team): implement S0 Cover scene for cyber/biz/sketch"
```

---

## Task 6: S1 AI 采用鸿沟 — 三版实现

**Files:**
- Create: `remotion-cyber/src/scenes/SceneGap.tsx`
- Create: `remotion-biz/src/scenes/SceneGap.tsx`
- Create: `remotion-sketch/src/scenes/SceneGap.tsx`
- Create: `remotion-cyber/src/scenes/svg/GlowBarChart.tsx` (Cyber 发光柱状图)
- Create: `remotion-biz/src/scenes/svg/HorizontalBarChart.tsx` (Biz 水平对比条)
- Create: `remotion-sketch/src/scenes/svg/HandDrawnBars.tsx` (Sketch 手绘柱图)

**视觉需求：**
- **Cyber**: 两段发光柱状图（88% vs 1%），鸿沟区域红光闪烁。GSAP 条形增长 + 鸿沟粒子断裂 + 数字脉冲
- **Biz**: 水平对比条形图，蓝色 vs 金色。Remotion 平滑增长 + 标注线逐条 + footnote 淡入
- **Skeelch**: 便利贴柱图，1% 那条有"?"标签。手绘条形 + 问号弹跳 + 分数线手写

**时长**: 3709 帧（123.64s）— 最长场景，需要分 Phase 展示多组数据

**步骤同 Task 5 模式：实现→更新路由→验证→提交**

---

## Task 7: S2 演化链 — 三版实现

**Files:**
- Create: `remotion-cyber/src/scenes/SceneEvolution.tsx` + SVG
- Create: `remotion-biz/src/scenes/SceneEvolution.tsx` + SVG
- Create: `remotion-sketch/src/scenes/SceneEvolution.tsx` + SVG

**视觉需求：**
- **Cyber**: 节点网络图，GSAP 路径动画 + 节点脉冲
- **Biz**: 三步流程箭头图，Remotion 渐进展开
- **Sketch**: 手绘箭头链 + strokeDashoffset 绘制

**时长**: 1583 帧（52.78s）

步骤模式同上。

---

## Task 8: S3 四特征 — 三版实现

**Files:**
- Create: 三个项目的 `SceneFourTraits.tsx` + 各自 SVG

**视觉需求：**
- **Cyber**: 四象限雷达图/能量核心，Anime.js 数据流旋转 + 中心脉冲
- **Biz**: 2×2 矩阵卡片，Remotion bounce 入场 + 描述逐字 fade
- **Sketch**: 手绘四格圆，strokeDashoffset 圆形路径绘制

**时长**: 3116 帧（103.88s）

---

## Task 9: S4 觉醒路径 — 三版实现

**Files:**
- Create: 三个项目的 `SceneAwaken.tsx` + 各自 SVG

**视觉需求：**
- **Cyber**: 三条发光路径（电路板走线），Anime.js 粒子流动 + 汇聚节点爆炸光芒
- **Biz**: 三栏并排时间线，Remotion 展开 + 里程碑图标 pop
- **Sketch**: 三条手绘蜿蜒路 + 灯泡"点亮"发光

**时长**: 1598 帧（53.28s）

---

## Task 10: S5 为何需要团队 — 三版实现

**Files:**
- Create: 三个项目的 `SceneWhyTeam.tsx` + 各自 SVG

**视觉需求：**
- **Cyber**: 四块拼图/四节点集群，GSAP 旋转飞入 + 缺口红光 + 完整后绿色锁定
- **Biz**: 四个圆形图标围绕中心标签，Remotion scale 入场 + 连线展开
- **Sketch**: 四个手绘积木堆叠，shake+drop 动画 + 缺块红色标注

**时长**: 1996 帧（66.52s）

---

## Task 11: S6 三种团队形态 — 三版实现

**Files:**
- Create: 三个项目的 `SceneForms.tsx` + 各自 SVG

**视觉需求（最复杂动画场景）：**
- **Cyber**: 节点网络图 ×3 形态变形（辐射型→网状→AI中枢），GSAP 变形动画 + 节点重排 + 连线溶解重连
- **Biz**: 三个组织架构图（树形→矩阵→星形），Remotion 渐显 + 滑动到位 + 连线绘制
- **Sketch**: 三个手绘组织图 + 不同颜色笔 + "翻页"切换

**时长**: 3354 帧（111.80s）— 第二长场景

**重要**: 此场景需分 Phase 渲染。建议每个形态约 37s，三 Phase 间有过渡动画。

---

## Task 12: S7 案例 — 三版实现

**Files:**
- Create: 三个项目的 `SceneCases.tsx` + 各自 SVG

**视觉需求：**
- **Cyber**: 三张全息卡片悬浮，GSAP 3D rotate 入场 + glow 效果 + 关键词高亮扫描
- **Biz**: 三张商务卡片（白底+色条+数据），Remotion slide-up + 计数器滚动
- **Sketch**: 三张便利贴（带图钉+手写标注），shake+drop 动画

**时长**: 1555 帧（51.82s）

---

## Task 13: S8 园丁收束 — 三版实现

**Files:**
- Create: 三个项目的 `SceneGardener.tsx` + 各自 SVG

**视觉需求：**
- **Cyber**: 数字花园——绿色粒子→树形网络生长，GSAP 粒子→树生长 + 阳光光束 + 行动清单 typewriter
- **Biz**: 渐变色带 + 行动清单图标列表，Remotion 色带展开 + 行动项 slide-in + CTA 放大
- **Sketch**: 手绘花盆→植物生长→花园，strokeDashoffset 花盆+枝叶 + 便利贴行动项

**时长**: 4121 帧（137.37s）— 最长场景之一

---

## Task 14: 全局验证与自检

**Step 1: 字号审计**

对所有 27 个场景组件检查：
- 正文 ≥42px
- SVG `<text>` ≥28px（3字以上 ≥32px）
- 封面标题 ≥120px
- 无硬编码颜色（全部来自 `theme`）

**Step 2: SVG viewBox 边界校验**

对含放射图/流程图的场景（S3、S4、S6）：
- 列出所有节点 (x, y) 坐标 + 元素尺寸
- 确认所有极值在 viewBox 范围内

**Step 3: 画布利用率检查**

在 Remotion Studio 逐场景预览：
- 主要内容区域占画布 ≥70%
- 无 >25% 的空白区域

**Step 4: SceneBackground 检查**

- 每个内页场景使用专属 aura 或 `<SceneBackground intensity={0.5} />`
- 跳到第 50 帧可见 ≥3 种动态元素（Cyber）/ 合适背景氛围（Biz/Sketch）

**Step 5: 音频同步验证**

- `npm run dev` 中跳到各场景首帧和末帧，验证画面与口播话题一致
- 对比 scene-boundaries.md 中的锚点 SRT 编号

**Step 6: 提交验证结果**

```bash
git add -A && git commit -m "feat(tencent-super-team): complete all 9 scenes × 3 styles with audit fixes"
```

---

## 通用模式与约定

### 场景组件文件命名

| Scene ID | 组件名 | 文件名 |
|----------|--------|--------|
| s0 | SceneCover | `scenes/SceneCover.tsx` |
| s1 | SceneGap | `scenes/SceneGap.tsx` |
| s2 | SceneEvolution | `scenes/SceneEvolution.tsx` |
| s3 | SceneFourTraits | `scenes/SceneFourTraits.tsx` |
| s4 | SceneAwaken | `scenes/SceneAwaken.tsx` |
| s5 | SceneWhyTeam | `scenes/SceneWhyTeam.tsx` |
| s6 | SceneForms | `scenes/SceneForms.tsx` |
| s7 | SceneCases | `scenes/SceneCases.tsx` |
| s8 | SceneGardener | `scenes/SceneGardener.tsx` |

### 场景组件标准模板

```tsx
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";
import { theme } from "../style-guide";
import { SceneBackground } from "../shared/SceneBackground";

interface SceneProps {
  sceneIndex: number;
  durationInFrames: number;
}

export const SceneXxx: React.FC<SceneProps> = ({ sceneIndex, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 动画编排...

  return (
    <AbsoluteFill style={{ backgroundColor: theme.colors.bg }}>
      {/* 背景层 */}
      <SceneBackground intensity={0.5} />

      {/* 内容层 */}
      <AbsoluteFill style={{ padding: `${theme.spacing.xl}px ${theme.spacing.section}px` }}>
        {/* 视觉隐喻 + 关键词 */}
      </AbsoluteFill>

      {/* 动画层 */}
    </AbsoluteFill>
  );
};
```

### 动画轨道选择

每个场景根据风格选择动画轨道：

| 风格 | 主要轨道 | 辅助轨道 | 入场 |
|------|---------|---------|------|
| Cyber | GSAP (`useGSAPTimeline`) | Anime.js (`useAnimeTimeline`) | Remotion spring |
| Biz | Remotion 原生 (`interpolate` + `spring`) | GSAP (`useGSAPTimeline`) 仅数字动画 | Remotion spring |
| Sketch | Remotion 原生 (`interpolate`) | Lottie (翻页/笔触) + `useStrokeReveal` | Remotion spring |

### 自检清单（每场景完成后）

- [ ] Remotion Studio 可预览，音频同步
- [ ] 引用 `theme` 对象，无硬编码颜色/字体
- [ ] 封面主视觉占画布 ≥50%; 标题 ≥120px
- [ ] SVG `<text>` ≥28px（3字以上 ≥32px）
- [ ] 画布利用率 ≥70%
- [ ] 内页有 SceneBackground 或专属 aura
- [ ] 步骤数与 SRT 口播内容对齐
- [ ] 有递进关系的场景使用箭头/连线而非纯卡片堆叠