# FDE 驻场工程师中视频 Remotion 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `fde-on-the-ground-mid-video` 开发 7 场工业风格 Remotion 场景，渲染交付 `production/videos/final_remotion_sub.mp4`。

**Architecture:** 复用 `remotion-pipelines` 共享基座（布局/动画/hooks/SceneBackground），覆写工业风色彩/字体系统，全场景 Lottie 主动画 + GSAP/Anime.js 文字编排。`audioConfig.ts` 为单一数据源，单音频模式。

**Tech Stack:** Remotion 4.x, React 18, TypeScript, Lottie (`@remotion/lottie` + `lottie-web`), GSAP 3.x, Anime.js 4.x, `@remotion/google-fonts`

**Design Doc:** `docs/plans/2026-06-04-fde-on-the-ground-remotion-design.md`

---

## Task 1: 初始化 Remotion 项目脚手架

**Files:**
- Create: `features/content-pipeline/fde-on-the-ground-mid-video/remotion/` (via `cli.mjs init`)
- Modify: `features/content-pipeline/fde-on-the-ground-mid-video/remotion/src/audioConfig.ts`
- Modify: `features/content-pipeline/fde-on-the-ground-mid-video/remotion/src/scenes/index.tsx`

**Step 1: 运行 CLI init 命令**

```bash
cd /Users/superno/Documents/code/creative/one-context/skills/remotion-pipelines
node cli.mjs init features/content-pipeline/fde-on-the-ground-mid-video/remotion/
```

这会从 `templates/default/` 复制完整脚手架 + `src/shared/` 到项目目录。

**Step 2: 安装依赖**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/fde-on-the-ground-mid-video/remotion
npm install
```

**Step 3: 拷贝 WAV 音频到 public/audio/**

```bash
mkdir -p public/audio
cp ../production/media/voiceover.wav public/audio/voiceover.wav
```

**Step 4: 创建 Lottie 资源目录**

```bash
mkdir -p public/lottie
touch public/lottie/.gitkeep
```

**Step 5: 验证 Remotion Studio 可启动**

```bash
npm run dev
```

预期：浏览器打开 Remotion Studio，显示占位场景。

**Step 6: Commit**

```bash
git add features/content-pipeline/fde-on-the-ground-mid-video/remotion/
git commit -m "feat(fde-video): init Remotion project scaffold"
```

---

## Task 2: 覆写工业风色彩与字体系统

**Files:**
- Modify: `remotion/src/shared/colors.ts`
- Modify: `remotion/src/shared/typography.ts`
- Modify: `remotion/src/shared/SceneBackground.tsx` (微调粒子色)
- Modify: `remotion/src/shared/index.ts` (确认导出)

**Step 1: 覆写 `colors.ts`**

```typescript
// 工业沉稳风色彩系统 — FDE 驻场工程师中视频
export const COLORS = {
  // 基础
  bg: "#0B1120",
  bgElevated: "#131B2E",
  text: "#E8ECF4",
  muted: "#8892A4",

  // 主强调 — 钢蓝（工程感）
  accent: "#4A9EFF",
  accentDim: "rgba(74, 158, 255, 0.15)",
  accentLit: "rgba(74, 158, 255, 0.05)",

  // 暖强调 — 金属铜（数据高亮）
  accentWarm: "#F0A050",
  accentWarmDim: "rgba(240, 160, 80, 0.15)",

  // 语义色
  success: "#3DDC84",
  danger: "#FF5252",

  // 渐变
  steelGradient: "linear-gradient(135deg, #1A2340, #2A3A5C)",
  metallic: "linear-gradient(90deg, #6B7B99, #AAB4C8, #6B7B99)",

  // 辩论光谱色（保留，按需使用）
  debateFast: "#6ec87a",
  debateMiddle: "#F0A050",
  debateSlow: "#7c8cf8",

  // SceneBackground 用
  alibabaBlue: "#4A9EFF",
  debateGreen: "#6ec87a",
} as const;
```

**Step 2: 覆写 `typography.ts`**

```typescript
// 工业风字体系统 — 无衬线为主
export const FONT = {
  chinese: '"Noto Sans SC", sans-serif',
  english: '"Inter", sans-serif',
  mono: '"JetBrains Mono", monospace',
} as const;

export const FONT_SIZE = {
  display: 180,
  hero: 108,
  lead: 84,
  title: 76,
  subtitle: 56,
  body: 48,
  label: 40,
  mono: 36,
} as const;
```

**Step 3: 在 `remotion.config.ts` 中注册 Google Fonts**

读取现有 `remotion.config.ts`，确保添加：

```typescript
import { Config } from "@remotion/cli/config";
// 暂不加 Google Fonts preload — 用 system fallback 先跑通
// 后续 Task 中添加 @remotion/google-fonts

const glRenderer = process.platform === "linux" ? "swiftshader" : "angle";
Config.setChromiumOpenGlRenderer(glRenderer);
```

**Step 4: 验证 Studio 启动无报错**

```bash
npm run dev
```

预期：编译成功，页面加载无红色错误。

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): override colors/typography to industrial theme"
```

---

## Task 3: 配置 audioConfig 并更新 SceneRouter

**Files:**
- Modify: `remotion/src/audioConfig.ts`
- Modify: `remotion/src/scenes/index.tsx`

**Step 1: 写入 audioConfig.ts**

基于 `scene-boundaries.md` 精确数据：

```typescript
// FDE 驻场工程师 — 7 场（按 SRT 锚点锁定 · 总长 389.52s）
// 来源：production/timing/scene-boundaries.md

export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

export const FPS = 30;
export const HAS_AUDIO = true;

export const SCENES: SceneConfig[] = [
  { id: "0", title: "封面 · 钩子+引入 FDE",            durationInFrames: 872,  audioFile: "audio/voiceover.wav" },
  { id: "1", title: "FDE 定义 · 不是售前",              durationInFrames: 2051, audioFile: "audio/voiceover.wav" },
  { id: "2", title: "典型一周 · 五步循环 + Discovery",  durationInFrames: 2869, audioFile: "audio/voiceover.wav" },
  { id: "3", title: "案例 John Deere",                  durationInFrames: 2394, audioFile: "audio/voiceover.wav" },
  { id: "4", title: "案例 Travelers",                    durationInFrames: 1630, audioFile: "audio/voiceover.wav" },
  { id: "5", title: "Morgan Stanley 模式",               durationInFrames: 1316, audioFile: "audio/voiceover.wav" },
  { id: "6", title: "角色对比表",                        durationInFrames: 554,  audioFile: "audio/voiceover.wav" },
];

export function getSceneStart(sceneIndex: number): number {
  return SCENES.slice(0, sceneIndex).reduce((sum, s) => sum + s.durationInFrames, 0);
}

export const TOTAL_FRAMES = SCENES.reduce((sum, s) => sum + s.durationInFrames, 0);
// 11686 帧 @ 30fps = 389.53s ≈ 6:29
```

**Step 2: 写入占位 SceneRouter with 7 scenes**

```typescript
import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { SCENES, getSceneStart, HAS_AUDIO } from "../audioConfig";
import { useCurrentSceneIndex } from "../hooks/useCurrentSceneIndex";
import { COLORS, FONT } from "../shared";

// 占位场景组件 — 逐步替换为实际场景
function PlaceholderScene({ index }: { index: number }) {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        color: COLORS.text,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT.chinese,
      }}
    >
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 120, color: COLORS.accent, marginBottom: 24 }}>
          {String(index + 1).padStart(2, "0")}
        </div>
        <div style={{ fontSize: 48 }}>{SCENES[index]?.title ?? ""}</div>
      </div>
    </AbsoluteFill>
  );
}

function SceneRouter({ id, index }: { id: string; index: number }) {
  switch (id) {
    // 逐步添加实际场景：
    // case "0": return <SceneCover />;
    // case "1": return <SceneDefine />;
    // case "2": return <SceneWeek />;
    // case "3": return <SceneDeere />;
    // case "4": return <SceneTravelers />;
    // case "5": return <SceneMorgan />;
    // case "6": return <SceneCompare />;
    default:
      return <PlaceholderScene index={index} />;
  }
}

const isSingleAudio = new Set(SCENES.map((s) => s.audioFile)).size === 1;

export const Video: React.FC = () => {
  useCurrentSceneIndex();

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      {SCENES.map((scene, idx) => (
        <Sequence key={scene.id} from={getSceneStart(idx)} durationInFrames={scene.durationInFrames}>
          <SceneRouter id={scene.id} index={idx} />
        </Sequence>
      ))}

      {HAS_AUDIO && isSingleAudio && (
        <Audio src={staticFile(SCENES[0].audioFile)} />
      )}
    </AbsoluteFill>
  );
};
```

**Step 3: 验证音频播放正常**

在 Remotion Studio 中跳转到不同场景时间点，确认口播音频在正确位置可听到。

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(fde-video): configure audioConfig for 7 scenes + placeholder SceneRouter"
```

---

## Task 4: 安装字体并添加 Lottie 依赖确认

**Files:**
- Modify: `remotion/package.json` (添加 `@remotion/google-fonts`)
- Modify: `remotion/src/Root.tsx` (注册字体)

**Step 1: 安装 Google Fonts 包**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/fde-on-the-ground-mid-video/remotion
npm install @remotion/google-fonts
```

**Step 2: 在 Root.tsx 中预加载字体**

```typescript
import React from "react";
import { Composition } from "remotion";
import { Video } from "./scenes/index";
import { TOTAL_FRAMES, FPS } from "./audioConfig";

// Google Fonts 预加载
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadNotoSansSC } from "@remotion/google-fonts/NotoSansSC";
import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";

loadInter();
loadNotoSansSC();
loadJetBrainsMono();

const CANVAS_W = 1920;
const CANVAS_H = 1080;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="SlideVideo"
      component={Video}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={CANVAS_W}
      height={CANVAS_H}
    />
  );
};
```

**Step 3: 验证字体加载无报错**

```bash
npm run dev
```

预期：控制台无字体加载错误，页面正常显示。

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(fde-video): add Google Fonts (Inter, Noto Sans SC, JetBrains Mono)"
```

---

## Task 5: SceneCover — 车间大门封面 (s0, 29.06s)

**Files:**
- Create: `remotion/src/scenes/SceneCover.tsx`
- Create: `remotion/src/scenes/svg/FactoryGate.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "0")

**设计对照** — 设计文档 §6 s0：
- Lottie 主动画：工厂门框从中央裂开，钢蓝光芒泄漏，六边形粒子飞散
- Anime.js 逐字描线：主标题「FDE 驻场工程师到底在干嘛」
- 副标题：`Forward Deployed Engineer · On the Ground` 淡入
- 背景：SceneBackground intensity=1.0 + 六边形网格

**Step 1: 创建 SVG 组件 `FactoryGate.tsx`**

实现工厂门框图形：
- SVG viewBox: 0 0 1920 1080
- 两扇门板，可接收 `openProgress` (0→1) prop 控制开合度
- 门内钢蓝光芒用 radialGradient 表达
- 六边形粒子用 `<circle>` 数组 + `interpolate(frame, ...)` 控制 opacity/position

**Step 2: 创建 `SceneCover.tsx`**

```typescript
// 核心结构：
// 1. SceneBackground intensity={1.0} hexGrid={true}
// 2. Lottie 层（或 SVG 门框动画作为 Lottie 未就绪时的 fallback）
// 3. 主标题 Anime.js splitText 逐字 reveal +钢蓝 fill
// 4. 副标题 interpolate fade-in
// 5. 封面主视觉占画布 50%+
```

注意：Lottie JSON 文件 `cover-gate.json` 需外部提供。在 Lottie 文件就绪前，用 SVG 门框动画 + Remotion 原生 `interpolate`/`spring` 实现 fallback。

关键动画时间线：
- 帧 0–300：门框裂开（`openProgress: 0→1`)
- 帧 200–500：光芒泄漏
- 帧 300+：主标题逐字 reveal
- 帧 400+：粒子飞散
- 帧 500+：副标题 fade-in

**Step 3: 在 SceneRouter 添加 case "0"**

```typescript
case "0": return <SceneCover />;
```

**Step 4: 验证封面场景**

在 Remotion Studio 中跳转到 s0（帧 0–871），确认：
- 门框动画流畅
- 标题 ≥120px（推荐 140-160px）
- 副标题清晰
- 背景动态可见

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s0 SceneCover — factory gate + title reveal"
```

---

## Task 6: SceneDefine — 不是售前，是驻场引擎 (s1, 68.38s)

**Files:**
- Create: `remotion/src/scenes/SceneDefine.tsx`
- Create: `remotion/src/scenes/svg/EngineGear.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "1")

**设计对照** — 设计文档 §6 s1：
- Lottie/ayout：左侧售前 PPT→❌ 覆盖，右侧引擎齿轮旋转→流水线节点逐亮
- 底部关键词 GSAP stagger：`驻场 → 大模型/智能体 → 可运行工作流 → 可量化评估`
- 背景：SceneBackground intensity=0.5 + scanBeam

**Step 1: 创建 `EngineGear.tsx`**

SVG 齿轮组件：
- 接收 `rotation`（度数）和 `glowProgress` (0→1) props
- 齿轮描线 + 中心光晕
- 流水线节点（5 个圆点 + 连线）接收 `activeNodes` 数组控制亮灭

**Step 2: 创建 `SceneDefine.tsx`**

核心布局：`AbsoluteFill` 内左右分区
- 左区（45%）："高级售前" 卡片 + PPT 图标 + ❌ 叠加层（灰色 muted）
- 右区（55%）：齿轮 + 流水线（accent 钢蓝高亮）
- 底部关键词条：使用 `useAnimeTimeline` 或 GSAP stagger 入场

动画分段（`useLottieSeek` 或 `interpolate` 分段控制）：
- 帧 0–900（0–30s）：左侧售前卡片淡入 → ❌ 叠加
- 帧 900–2051（30–68s）：右侧齿轮旋转 → 节点逐亮 → 底部关键词

**Step 3: 在 SceneRouter 添加 case "1"**

**Step 4: 验证 s1 场景**

确认 SplitLayout/左右分区视觉效果、卡片文字 ≥42px、SVG 文字 ≥28px。

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s1 SceneDefine — not presales, deployed engine"
```

---

## Task 7: SceneWeek — 五步循环引擎 + Discovery (s2, 95.62s) ⭐ 最长

**Files:**
- Create: `remotion/src/scenes/SceneWeek.tsx`
- Create: `remotion/src/scenes/svg/PipelineFlow.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "2")

**设计对照** — 设计文档 §6 s2：
- 横向五阶段流程：`发现 → 原型 → 合规联调 → 上线 → 迭代`
- 每阶段图标：放大镜、齿轮/扳手、盾牌、火箭、循环箭头
- Discovery 子图下拉展开：访谈 → 调研权限 → 流程图/优先级矩阵/价值热力图
- 背景：SceneBackground intensity=0.4 + circuits

**Step 1: 创建 `PipelineFlow.tsx`**

SVG 五步流程组件：
- 5 个节点 + 箭头连线
- 每节点接收 `activeProgress` 控制高亮
- 图标用简单 SVG path（放大镜、齿轮、盾牌、火箭、循环箭头）
- viewBox: ~1600×400（横向展开）
- 连线用 `useStrokeReveal` 描线

**Step 2: 创建 `SceneWeek.tsx`**

核心布局：全幅横向流程图 + 底部注释区

三段动画（用 `interpolate` 切换 Phase）：
- Phase 1（帧 0–600, 0–20s）：齿轮组启动，五个节点初步显示
- Phase 2（帧 600–1650, 20–55s）：五阶段逐一高亮 + 连线描线
- Phase 3（帧 1650–2869, 55–96s）：Discovery 子图从「发现」节点下拉展开

关键数据：SRT #38 起始，关注口播中的步骤对应。

**Step 3: 在 SceneRouter 添加 case "2"**

**Step 4: 验证 s2 场景**

确认三个 Phase 流畅切换、Discovery 子图不遮挡主流程、所有 SVG text ≥28px。

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s2 SceneWeek — 5-step cycle + Discovery"
```

---

## Task 8: SceneDeere — 精准喷射漏斗 (s3, 79.80s)

**Files:**
- Create: `remotion/src/scenes/SceneDeere.tsx`
- Create: `remotion/src/scenes/svg/FunnelDiagram.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "3")

**设计对照** — 设计文档 §6 s3：
- 漏斗三层：领域专家审核 → 自定义 Evals → AI 精准推荐
- 数据卡 GSAP 弹出：左 `-70%` 化学用量(success)、右 `6×` 客户互动(accentWarm)
- 底部：自然语言交互示意（对话气泡 → 设备图标）
- 背景：SceneBackground intensity=0.3 + dataStreams

**Step 1: 创建 `FunnelDiagram.tsx`**

SVG 漏斗组件：
- 三层倒梯形，用 clipPath 或 polygon 表达
- 每层接收 `fillProgress` 控制填充动画
- viewBox: ~800×700（纵向展开）

**Step 2: 创建 `SceneDeere.tsx`**

核心布局：左侧漏斗（55%）+ 右侧数据卡栏（45%）
- 数据数字使用 `FONT.mono` + 大字号（≥80px）
- 底部对话气泡用简单 SVG

**Step 3: 在 SceneRouter 添加 case "3"**

**Step 4: 验证 s3 场景**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s3 SceneDeere — precision funnel + data cards"
```

---

## Task 9: SceneTravelers — 地图 Rollout 扩散 (s4, 54.32s)

**Files:**
- Create: `remotion/src/scenes/SceneTravelers.tsx`
- Create: `remotion/src/scenes/svg/USMap.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "4")

**设计对照** — 设计文档 §6 s4：
- 美国地图 SVG（简化轮廓）+ 8 州亮点 → 涟漪扩散 → 全图填充
- 右侧数据卡：`150万+ /年理赔`、`$230亿+ 赔付`、`85-90% 采纳率`
- 底部：`AI Claim Assistant · Realtime API`
- 背景：SceneBackground intensity=0.4 + particles

**Step 1: 创建 `USMap.tsx`**

SVG 美国地图组件：
- 简化轮廓 path（可用 d3-geo 简化数据或手动 Path）
- 8 个亮点坐标（简化）
- 接收 `phase` prop：'pilot' | 'ripple' | 'full'
- 涟漪扩散用 `<circle>` + `interpolate` radius/opacity

**Step 2: 创建 `SceneTravelers.tsx`**

核心布局：左侧地图（60%）+ 右侧数据卡（40%）

动画三段：
- Phase 1（帧 0–600, 0–20s）：8 州亮点弹簧入场
- Phase 2（帧 600–1200, 20–40s）：涟漪扩散动画
- Phase 3（帧 1200–1630, 40–54s）：全图渐变填充 accent 色 + 数据卡出现

**Step 3: 在 SceneRouter 添加 case "4"**

**Step 4: 验证 s4 场景**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s4 SceneTravelers — map rollout + data cards"
```

---

## Task 10: SceneMorgan — 信任建设时间线 (s5, 43.86s)

**Files:**
- Create: `remotion/src/scenes/SceneMorgan.tsx`
- Create: `remotion/src/scenes/svg/TrustTimeline.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "5")

**设计对照** — 设计文档 §6 s5：
- 横向时间线 4 节点：研报 RAG ✅ → Evals+护栏 → 数月试点 ⏳ → 98% 采纳 ✅
- 连线 Anime.js 描线
- 底部标注：`公开访谈整理（Colin Jarvis）· 非 OpenAI 案例页`
- 背景：SceneBackground intensity=0.3 + orbits

**Step 1: 创建 `TrustTimeline.tsx`**

SVG 时间线组件：
- 4 个圆形节点 + 连线
- 节点接收 `activeIndex` 控制亮灭状态
- ✅ 对勾和 ⏳ 脉冲动画
- viewBox: ~1400×300

**Step 2: 创建 `SceneMorgan.tsx`**

核心布局：全幅时间线（上 60%）+ 数据/标注区（下 40%）

动画逐节点推进（每节点约 10s / 300 帧）：
- 节点 1（帧 0–330）：研报 RAG 钢蓝高亮 + 连线描线
- 节点 2（帧 330–660）：Evals+护栏 灰→亮
- 节点 3（帧 660–990）：数月试点 金属铜色脉冲
- 节点 4（帧 990–1316）：98% 采纳 success 绿 + 对勾

**Step 3: 在 SceneRouter 添加 case "5"**

**Step 4: 验证 s5 场景**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s5 SceneMorgan — trust timeline"
```

---

## Task 11: SceneCompare — 四列对比仪表盘 (s6, 18.48s)

**Files:**
- Create: `remotion/src/scenes/SceneCompare.tsx`
- Create: `remotion/src/scenes/svg/DashboardGrid.tsx`
- Modify: `remotion/src/scenes/index.tsx` (添加 case "6")

**设计对照** — 设计文档 §6 s6：
- 四列对比表：FDE / AI Engineer / 咨询 / SE
- 行：重心、交付物、成功标准、驻场
- FDE 列整列钢蓝高亮，其他列 muted
- GSAP stagger 入场：列从左到右 80ms 间隔
- 背景微光 Lottie 或 SceneBackground intensity=0.2

**Step 1: 创建 `DashboardGrid.tsx`**

SVG 仪表盘网格组件：
- 4 列 × 4 行的网格
- 接收 `visibleColumns` 数组控制渐次显示
- FDE 列高亮样式

**Step 2: 创建 `SceneCompare.tsx`**

核心布局：全幅四列对比表（信息密集，18s 快节奏）

使用 `useAnimeSeek` 或 `interpolate` 实现列 stagger：
- 帧 0–100：标题 + 表头
- 帧 100–400：4 列从左到右间隔 8 帧入场
- 帧 400–554：全表展示 + FDE 列脉冲高亮

关键数据（来自 SRT #165–173）：

| | FDE | AI Engineer | 咨询 | SE |
|---|---|---|---|---|
| 重心 | 客户现场 | 内部平台 | 战略建议 | 产品演示 |
| 交付物 | 可运行工作流 | 平台/工具 | 报告/PPT | Demo |
| 成功标准 | 真正跑起来 | 系统指标 | 客户满意 | 成单 |
| 驻场 | 长期 | 偶尔 | 短期 | 无 |

**Step 3: 在 SceneRouter 添加 case "6"**

**Step 4: 验证 s6 场景**

确认 18s 内 4 列均可读、FDE 列高亮明显、文字 ≥42px。

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): s6 SceneCompare — 4-column dashboard"
```

---

## Task 12: 集成 Lottie 主动画（外部 JSON 就绪后）

**前置条件**：7 个 Lottie JSON 文件已放置到 `public/lottie/` 目录。

**Files:**
- Create: `remotion/public/lottie/*.json` (7 个文件)
- Modify: 各 `SceneXxx.tsx` — 在 SVG fallback 旁添加 Lottie 层

**Step 1: 验证 Lottie JSON 自包含性**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/fde-on-the-ground-mid-video/remotion
# 检查 JSON 中无远程资源引用
for f in public/lottie/*.json; do
  echo "=== $f ==="
  grep -c '"p"' "$f" || echo "No image references"
  grep -c '"u"' "$f" || echo "No URL references"
done
```

预期：所有 `"p"` 和 `"u"` 字段应为空字符串或相对路径。

**Step 2: 在 s0 SceneCover 中集成 Lottie**

```typescript
import coverGateJson from "../../public/lottie/cover-gate.json";
import { Lottie } from "@remotion/lottie";

// 在组件中：
<Lottie
  animationData={coverGateJson}
  style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}
  loop={false}
  playbackRate={1}
/>
```

对 s1/s2/s4/s5（需要分段控制），使用 `useLottieSeek`：

```typescript
import { useLottieSeek } from "../shared/animations/lottie";
import defineEngineJson from "../../public/lottie/define-engine.json";

const ref = useLottieSeek(
  useCallback((root) => {
    return lottie.loadAnimation({
      container: root,
      renderer: "svg",
      loop: false,
      autoplay: false,
      animationData: defineEngineJson,
    });
  }, []),
);
```

**Step 3: 逐场景集成，保留 SVG fallback**

每个场景保留现有 SVG 动画作为 fallback（注释掉或条件渲染），Lottie 层叠加在其上方或替换。

**Step 4: 验证 Lottie 帧对齐**

对每个场景：
1. 跳转到场景起始帧
2. 检查 Lottie 动画起始位置正确
3. 跳转到场景结束帧，检查 Lottie 停在最后一帧
4. 如不对齐，调整 `playbackRate` 或修改 Lottie JSON 帧数

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): integrate Lottie animations for all 7 scenes"
```

---

## Task 13: 渲染、烧录字幕与成片自检

**Files:**
- Create: `production/videos/final_remotion.mp4`
- Create: `production/videos/final_remotion_sub.mp4`
- Modify: `production/timing/wav-durations.json` (确认同步)

**Step 1: 确认 wav-durations.json 与 audioConfig.ts 同步**

```json
{
  "wavFile": "media/voiceover.wav",
  "slideDurationsSec": [29.06, 68.38, 95.62, 79.8, 54.32, 43.86, 18.48],
  "outputFile": "videos/final_remotion_sub.mp4",
  "burnSubtitles": true,
  "srtFile": "subtitles/sub.srt",
  "subtitle": {
    "fontSize": 60,
    "charsPerLine": 22,
    "barHeight": 0
  }
}
```

**Step 2: 渲染无字幕 MP4**

```bash
cd /Users/superno/Documents/code/creative/one-context/features/content-pipeline/fde-on-the-ground-mid-video/remotion
mkdir -p ../production/videos
npm run render
```

预期：`production/videos/final_remotion.mp4` 生成，时长约 6:29。

**Step 3: 烧录字幕**

```bash
npm run burn-sub
```

预期：`production/videos/final_remotion_sub.mp4` 生成，字幕可读。

**Step 4: 成片自检（按 SKILL.md 门控清单）**

- [ ] `scene-boundaries.md` 与 `audioConfig.ts` / `slideDurationsSec` 一致，总和 ≈ WAV 时长
- [ ] 试听 3 个锚点时刻（s1 SRT#11, s2 SRT#38, s3 SRT#81）——画面话题与口播一致
- [ ] 存在 `final_remotion_sub.mp4` 且字幕可读（60px、barHeight=0）
- [ ] 各 Scene 可见正文 ≥42px
- [ ] SVG `<text>` 字号 ≥28px（3字以上 ≥32px）
- [ ] 主要内容区域占画布 ≥70%
- [ ] 每个内页场景使用 SceneBackground 或专属 aura
- [ ] 封面有前景主视觉元素且面积 ≥ 画布 50%
- [ ] 封面标题 ≥120px
- [ ] 口播枚举的关键信息在画面有对应视觉元素

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(fde-video): render + burn subtitles + self-check complete"
```

---

## Task 14: 更新 production 产出文件

**Files:**
- Modify: `production/content/05-publish-kit.md`
- Modify: `production/timing/flip-checklist.md`

**Step 1: 更新 05-publish-kit.md**

确认视频产出路径、时长、场景数已更新。

**Step 2: 更新 flip-checklist.md**

标记 Remotion 场景渲染完成。

**Step 3: Commit**

```bash
git add -A
git commit -m "docs(fde-video): update production output files"
```

---

## 关键注意事项

1. **Lottie JSON 来源**：7 个 Lottie 动画文件需外部提供（AE 导出或采购），放置到 `public/lottie/` 目录。Task 5–11 先用 SVG + Remotion 原生动画作为 fallback，Task 12 在 Lottie JSON 就绪后集成。

2. **SKILL.md 约束**：
   - 字号硬约束：正文 ≥42px，卡片标题 ≥52px，SVG `<text>` ≥28px（3字+ ≥32px），封面标题 ≥120px
   - 画布利用率：主要内容区域 ≥70%
   - 封面必有前景主视觉（≥50% 画布）
   - 内页必须有动态背景（SceneBackground 或专属 aura）
   - 单 Scene 择一动画引擎（不挂双引擎 hook），Lottie 与其他轨可并存不同根节点
   - Lottie `autoplay: false`，`loop: false`

3. **逐句心象法**：每个场景开发前，先读对应 SRT 段落，确认画面覆盖口播中所有关键名词/数字/因果。

4. **SVG viewBox 边界校验**：写完每个 SVG 组件后静态校验坐标范围。

5. **二级渐进揭示**：结构框架先入场，内容条目延迟 10-15 帧逐一出现。