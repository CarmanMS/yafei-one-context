# Remotion 音画对齐重设计 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 tencent-super-team-mid-video Remotion 项目从 9 场景改为 12 场景，使视觉内容与字幕音频完全对齐。

**Architecture:** 修改 `audioConfig.ts` 配置驱动的场景时长 + `scenes/index.tsx` 路由器映射 + 逐一重写/新增 Scene 组件。沿用现有赛博朋克视觉风格和 GSAP/anime.js 动画框架。单 WAV 音频不变。

**Tech Stack:** Remotion 4.x, React 18, TypeScript, GSAP 3.x, anime.js 4.x, `shared/SceneBackground` + `style-guide.ts` 颜色/字体体系

**设计文档:** `docs/plans/2026-06-04-remotion-audio-visual-alignment-design.md`

**项目根:** `features/content-pipeline/tencent-super-team-mid-video/remotion-cyber`

---

## Task 1: 更新 audioConfig.ts — 12 场景时长配置

**Files:**
- Modify: `src/audioConfig.ts`

**Step 1: 替换 DURATIONS 和 TITLES 数组**

将 `src/audioConfig.ts` 的内容替换为：

```typescript
// audioConfig.ts — 腾讯超级团队中视频
export interface SceneConfig {
  id: string;
  title: string;
  durationInFrames: number;
  audioFile: string;
}

const FPS = 30;
const AUDIO_FILE = "audio/voiceover.wav";

// 12-scene alignment with subtitle audio (2026-06-04 redesign)
const DURATIONS = [
  14.56,   // s0  封面
  63.08,   // s1  AI采用鸿沟
  60.56,   // s2  竞争力公式
  48.36,   // s3  演化链
  41.96,   // s4  四大特征
  63.74,   // s5  生产力数据
  53.74,   // s6  觉醒路径
  68.02,   // s7  为何需要团队
  53.16,   // s8  三种形态
  108.84,  // s9  运作+案例
  67.46,   // s10 园丁管理
  71.74,   // s11 问题+收束
];
const TITLES = [
  "封面", "AI采用鸿沟", "竞争力公式", "演化链", "四大特征",
  "生产力数据", "觉醒路径", "为何需要团队", "三种形态",
  "运作+案例", "园丁管理", "问题+收束",
];

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

**Step 2: 验证编译**

Run: `cd features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npx tsc --noEmit src/audioConfig.ts`

Expected: 无错误

**Step 3: Commit**

```bash
git add src/audioConfig.ts
git commit -m "refactor: update audioConfig to 12-scene alignment with audio"
```

---

## Task 2: 更新 scenes/index.tsx — 12 场景路由

**Files:**
- Modify: `src/scenes/index.tsx`

**Step 1: 替换 SceneRouter 和导入**

将 `src/scenes/index.tsx` 的内容替换为：

```typescript
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
} from "remotion";
import { SCENES, getSceneStart } from "../audioConfig";
import { useCurrentSceneIndex } from "../hooks/useCurrentSceneIndex";
import { SceneCover } from "./SceneCover";
import { SceneGap } from "./SceneGap";
import { SceneFormula } from "./SceneFormula";
import { SceneEvolution } from "./SceneEvolution";
import { SceneFourTraits } from "./SceneFourTraits";
import { SceneData } from "./SceneData";
import { SceneAwaken } from "./SceneAwaken";
import { SceneWhyTeam } from "./SceneWhyTeam";
import { SceneForms } from "./SceneForms";
import { SceneCases } from "./SceneCases";
import { SceneGardener } from "./SceneGardener";
import { SceneClosing } from "./SceneClosing";

/**
 * Audio 适配层：根据 SCENES 中 audioFile 的一致性自动判断模式。
 * - 所有 scene 的 audioFile 相同 → single 模式（方案 A）：播放一个完整 WAV
 * - 不同 → split 模式（方案 B）：每场景播放各自的音频
 */
const isSingleAudio = new Set(SCENES.map((s) => s.audioFile)).size === 1;

/**
 * 场景路由器：根据 scene.id 路由到对应的场景组件。
 */
function SceneRouter({ id }: { id: string; index: number }) {
  switch (id) {
    case "s0":  return <SceneCover />;
    case "s1":  return <SceneGap />;
    case "s2":  return <SceneFormula />;
    case "s3":  return <SceneEvolution />;
    case "s4":  return <SceneFourTraits />;
    case "s5":  return <SceneData />;
    case "s6":  return <SceneAwaken />;
    case "s7":  return <SceneWhyTeam />;
    case "s8":  return <SceneForms />;
    case "s9":  return <SceneCases />;
    case "s10": return <SceneGardener />;
    case "s11": return <SceneClosing />;
    default:
      return (
        <AbsoluteFill style={{ backgroundColor: "#0a0a0b", display: "flex", alignItems: "center", justifyContent: "center", color: "#f1efea" }}>
          <div>Unknown scene: {id}</div>
        </AbsoluteFill>
      );
  }
}

/**
 * 主视频组件：场景编排 + Audio 适配
 */
export const Video: React.FC = () => {
  useCurrentSceneIndex();

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0b" }}>
      {SCENES.map((scene, idx) => (
        <Sequence
          key={scene.id}
          from={getSceneStart(idx)}
          durationInFrames={scene.durationInFrames}
        >
          <SceneRouter id={scene.id} index={idx} />
        </Sequence>
      ))}

      {isSingleAudio ? (
        <Audio src={staticFile(SCENES[0].audioFile)} />
      ) : (
        SCENES.map((scene, idx) => (
          <Sequence key={scene.id} from={getSceneStart(idx)} durationInFrames={scene.durationInFrames}>
            <Audio src={staticFile(scene.audioFile)} />
          </Sequence>
        ))
      )}
    </AbsoluteFill>
  );
};
```

**Step 2: 创建 3 个占位新场景文件**

新建 `src/scenes/SceneFormula.tsx`：

```typescript
import React from "react";
import { AbsoluteFill } from "remotion";

export const SceneFormula: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#0a0a0b", display: "flex", alignItems: "center", justifyContent: "center", color: "#00f5d4" }}>
    <div>S2 · 竞争力公式 (placeholder)</div>
  </AbsoluteFill>
);
```

新建 `src/scenes/SceneData.tsx`：

```typescript
import React from "react";
import { AbsoluteFill } from "remotion";

export const SceneData: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#0a0a0b", display: "flex", alignItems: "center", justifyContent: "center", color: "#00f5d4" }}>
    <div>S5 · 生产力数据 (placeholder)</div>
  </AbsoluteFill>
);
```

新建 `src/scenes/SceneClosing.tsx`：

```typescript
import React from "react";
import { AbsoluteFill } from "remotion";

export const SceneClosing: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#0a0a0b", display: "flex", alignItems: "center", justifyContent: "center", color: "#00f5d4" }}>
    <div>S11 · 问题+收束 (placeholder)</div>
  </AbsoluteFill>
);
```

**Step 3: 验证编译 + Remotion Studio 启动**

Run: `cd features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npx tsc --noEmit`

Expected: 无错误。12 个场景全部路由成功。

Run: `cd features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npm run dev`

Expected: Remotion Studio 启动，12 个场景均可跳转（3 个 placeholder 显示占位文字）。

**Step 4: Commit**

```bash
git add src/scenes/index.tsx src/scenes/SceneFormula.tsx src/scenes/SceneData.tsx src/scenes/SceneClosing.tsx
git commit -m "refactor: update scene router to 12 scenes with 3 placeholders"
```

---

## Task 3: s0 SceneCover — 微调副标题

**Files:**
- Modify: `src/scenes/SceneCover.tsx`

**Step 1: 更新副标题文本**

在 `SceneCover.tsx` 中找到 `<Subtitle>` 组件或副标题文字，将现有副标题改为：
```
AI 如何重塑个体与组织的未来
```

同时确认公式显示为 `组织竞争力 = 人才密度 × AI杠杆 ÷ 组织摩擦`。

**Step 2: 验证渲染**

Run: `npm run dev` → 跳转 s0 → 确认副标题和公式文字正确。

**Step 3: Commit**

```bash
git add src/scenes/SceneCover.tsx
git commit -m "fix(s0): update cover subtitle to match audio intro"
```

---

## Task 4: s1 SceneGap — 扩展 P2 鸿沟深因 + P3 涌现

**Files:**
- Modify: `src/scenes/SceneGap.tsx`

**改动说明：**

1. 更新 `PHASES` 常量以匹配新的 63.08s 时长（1892帧 @30fps）：
   - P1: 0-1110 帧 (0-37s) — 88% vs 1% 数据冲击 + 鸿沟
   - P2: 1110-1500 帧 (37-50s) — 鸿沟深因
   - P3: 1500-1892 帧 (50-63s) — 涌现动画

2. 保留现有 `VerticalBarChart`、`DataParticles` 组件用于 P1。

3. 删除现有 `Phase3Analysis`（3张卡片）和 `Phase4Conclusion`（结论文字）。

4. **新增 `Phase2DeepCause` 组件**：
   - 三条横条从左到右展开动画：「协作方式」「决策机制」「价值创造模式」
   - 每条展开后 × 红叉划过动画
   - 底部文字：「更深层次的东西，几乎没有什么改变」
   - 使用 GSAP `useGSAPTimeline` 实现横条入场 + 红叉动画

5. **新增 `Phase3Emergence` 组件**：
   - 屏幕底部 80px 区域绘制网格线
   - 30+ 个小光点（直径 2-4px）从底部随机位置向上涌动
   - 光点汇聚到屏幕中央偏上位置，形成向上箭头轮廓
   - 中央文字淡入：「真正的AI变革是自下而上的涌现」
   - 使用 Remotion `interpolate` + 随机种子粒子位置（`useMemo` 固定位置）

6. 在 `SceneGap` 主组件中按 phase 可见性切换 P1/P2/P3。

**Step 2: 验证渲染**

Run: `npm run dev` → 跳转 s1 → 播放确认三个 phase 的过渡动画。

**Step 3: Commit**

```bash
git add src/scenes/SceneGap.tsx
git commit -m "feat(s1): add P2 deep cause + P3 emergence animation for gap scene"
```

---

## Task 5: s2 SceneFormula — 全新竞争力公式场景

**Files:**
- Modify: `src/scenes/SceneFormula.tsx`（替换占位）

**改动说明：**

1. 更新 PHASES（1817帧 / 60.56s）：
   - P1: 0-450 帧 (0-15s) — 腾讯10关键词星云
   - P2: 450-900 帧 (15-30s) — 公式展开
   - P3: 900-1500 帧 (30-50s) — 三要素详解卡片
   - P4: 1500-1817 帧 (50-60s) — 结论

2. **`KeywordsNebula` 组件**：10 个关键词节点从屏幕四周飘入中央。使用 `interpolate` 控制每节点入场时间（stagger 10帧）。节点散布在中央 400×400 区域。顶部标注文字「腾讯研究院 · AI原生小组 · 2026.5.15」。关键词列表（从音频）：价域、工程、技艺、技能、涌现、杠杆、密度、原生、协同、涌现（以字幕实际为准，音频提及"包括价域、工程、技艺、技能等等"）。

3. **`FormulaReveal` 组件**：中央大字公式 `组织竞争力 = 人才密度 × AI杠杆 ÷ 组织摩擦`。逐段显现：先 `组织竞争力 =`，再 `人才密度`，再 `×`，再 `AI杠杆`，再 `÷`，再 `组织摩擦`。乘号和除号用 `theme.colors.accent` 高亮。每个符号停留 5 帧后继续。使用 GSAP timeline。

4. **`ElementCards` 组件**：三张竖排信息卡，依次交替高亮：
   - 人才密度 → 「独立闭环完成任务的人数比」
   - AI杠杆 → 「AI融入工作流程的深度广度」
   - 组织摩擦 → 「等待+审批+对齐的损耗」
   - 高亮的卡片有 `theme.colors.glow` 光晕，非高亮卡片 desaturate。

5. **`ConclusionFlash` 组件**：公式分母（组织摩擦）闪烁红色。底部文字：「不是加法，是乘除法」。

6. 使用 `SceneBackground intensity={0.5} hexGrid={false}` 背景和 `SceneLabel "S2 · 竞争力公式"`。

**Step 2: 验证编译**

Run: `npx tsc --noEmit`

**Step 3: 验证渲染**

Run: `npm run dev` → s2 → 确认四 phase 视觉效果。

**Step 4: Commit**

```bash
git add src/scenes/SceneFormula.tsx
git commit -m "feat(s2): implement competitiveness formula scene with 4 phases"
```

---

## Task 6: s3 SceneEvolution — 3→4 节点 + 术语重写

**Files:**
- Modify: `src/scenes/SceneEvolution.tsx`

**改动说明：**

1. 更新 PHASES（1451帧 / 48.36s）：
   - P1: 0-540 帧 (0-18s) — 第1-2节点
   - P2: 540-1080 帧 (18-36s) — 第3节点
   - P3: 1080-1451 帧 (36-48s) — 第4节点

2. 替换 `NODES` 数据：

```typescript
const NODES: NodeData[] = [
  {
    id: "node1",
    title: "知识工作者",
    subItems: ["德鲁克 · 60年代", "靠知识创造价值", "必须依托组织平台"],
    color: theme.colors.secondary,
    glowColor: theme.colors.glowSecondary,
    x: 12.5,
  },
  {
    id: "node2",
    title: "创意阶层",
    subItems: ["佛罗里达 · 2002", "不仅处理信息", "还要产生新想法"],
    color: theme.colors.primary,
    glowColor: theme.colors.glow,
    x: 37.5,
  },
  {
    id: "node3",
    title: "一人公司",
    subItems: ["贾贝斯 · 2019", "独立运作生意", "但能力有上限"],
    color: "#FFD700",
    glowColor: "rgba(255, 215, 0, 0.3)",
    x: 62.5,
  },
  {
    id: "node4",
    title: "AI超级个体",
    subItems: ["NOW", "AI调度·全局任务", "能力边界延展"],
    color: theme.colors.accent,
    glowColor: `rgba(255, 71, 87, 0.3)`,
    x: 87.5,
  },
];
```

3. 更新时间线指示器(TimelineIndicator)为 4 个 phase 点。

4. 底部文字更新为「从知识工作者到AI超级个体的四阶段演变」。

5. P3 中 node4 的光晕需要更大更亮，可使用 `boxShadow` 扩散到相邻区域。

**Step 2: 验证渲染**

Run: `npm run dev` → s3 → 确认4节点时间线。

**Step 3: Commit**

```bash
git add src/scenes/SceneEvolution.tsx
git commit -m "feat(s3): rewrite evolution chain to 4 nodes with correct terminology"
```

---

## Task 7: s4 SceneFourTraits — 四特征全换

**Files:**
- Modify: `src/scenes/SceneFourTraits.tsx`

**改动说明：**

1. 更新 PHASES（1259帧 / 41.96s）：
   - P1: 0-660 帧 (0-22s) — 前两特征
   - P2: 660-1259 帧 (22-42s) — 后两特征+全局

2. 替换 `TRAITS` 数据：

```typescript
const TRAITS: TraitData[] = [
  {
    id: "trait1",
    title: "AI-first",
    description: "默认工作方式从AI开始\n不是遇难题才求助AI",
    color: theme.colors.primary,
    glowColor: theme.colors.glow,
    quadrant: 0,
  },
  {
    id: "trait2",
    title: "能力跃迁",
    description: "一人从想法到交付\n效率10倍甚至更多",
    color: theme.colors.secondary,
    glowColor: theme.colors.glowSecondary,
    quadrant: 1,
  },
  {
    id: "trait3",
    title: "主动探索",
    description: "主动探索扩展能力边界\n不断突破自身限制",
    color: theme.colors.accent,
    glowColor: `rgba(255, 71, 87, 0.3)`,
    quadrant: 2,
  },
  {
    id: "trait4",
    title: "影响力溢出",
    description: "不只自己快\n还带团队一起提升\n——这是分水岭",
    color: "#FFD700",
    glowColor: "rgba(255, 215, 0, 0.3)",
    quadrant: 3,
  },
];
```

3. 更新 P4 汇总文字：`四大特征 · AI超级个体的真正标志`。

4. 「影响力溢出」卡片需额外视觉标记——可用脉冲光环或边框闪光标注「分水岭」。

**Step 2: 验证渲染**

Run: `npm run dev` → s4 → 确认四特征内容。

**Step 3: Commit**

```bash
git add src/scenes/SceneFourTraits.tsx
git commit -m "feat(s4): replace 4 traits with AI-first/leap/explore/spillover"
```

---

## Task 8: s5 SceneData — 全新生产力数据场景

**Files:**
- Modify: `src/scenes/SceneData.tsx`（替换占位）

**改动说明：**

1. PHASES（1912帧 / 63.74s）：
   - P1: 0-540 帧 (0-18s) — 任务缩短数据
   - P2: 540-990 帧 (18-33s) — 叠加 vs 重设计对比
   - P3: 990-1500 帧 (33-50s) — Cursor 增长曲线
   - P4: 1500-1912 帧 (50-63s) — 单人公司趋势

2. **`TimeReduction` 组件**：中央大数字 `80%` 以 `interpolate` 从 0 跳动到 80，上方小字 `Anthropic · 10万条对话`。左侧小字 `信息检索 95%`、右侧 `课程开发 96%` 依次淡入。

3. **`StrategyCompare` 组件**：左右两个面板。左面板蓝色：`简单叠加 → 20~40%`（温和增长条）。右面板橙色：`围绕AI Agent重设计 → 2~10x`（陡增曲线 + 光晕）。使用 `theme.colors.secondary` 和 `theme.colors.accent`。

4. **`CursorGrowth` 组件**：SVG 绘制陡峭增长曲线。横轴标注 12 个月刻度。纵轴从 $1M 到 $100M。右上角标注 `60人 / $300M ARR`。曲线使用 `useStrokeReveal` 或 `useGSAPTimeline` 描绘动画。

5. **`SoloFounderTrend` 组件**：两根柱状条对比——2019 `23.7%` vs 2025 `36.3%`。趋势箭头从左柱顶部斜向右上。标注 `Karta 2025`。

6. 使用 `SceneBackground intensity={0.5} hexGrid={false}` + `SceneLabel "S5 · 生产力数据"`。

**Step 2: 验证编译+渲染**

Run: `npx tsc --noEmit && npm run dev` → s5

**Step 3: Commit**

```bash
git add src/scenes/SceneData.tsx
git commit -m "feat(s5): implement productivity data scene with 4 phases"
```

---

## Task 9: s6 SceneAwaken — 标签+描述更新

**Files:**
- Modify: `src/scenes/SceneAwaken.tsx`

**改动说明：**

1. 更新 PHASES（1612帧 / 53.74s）：
   - P1: 0-540 帧 (0-18s) — 工程师
   - P2: 540-1080 帧 (18-36s) — 非工程师
   - P3: 1080-1612 帧 (36-53s) — 创始人

2. 替换 `paths` 数据中的 title/subtitle：

```typescript
// path 1: 开发者
title: "工程师觉醒",
subtitle: "从写代码到指挥代码",
```

```typescript
// path 2: 非工程师
title: "非工程师觉醒",
subtitle: "从单一执行到全栈交付",
```

```typescript
// path 3: 创始人
title: "创始人觉醒",
subtitle: "从提需求到下场 build",
```

3. **PathLabel 增强**：每条路径在副标题下方增加数据信息：
   - path 1: 数据胶囊 `「90%+ AI生成」「一晚 ≈ 10,000 行」`，引用框 `「AI是中心，所有人都是边缘」`
   - path 2: 三个小圆交汇图标 `产品设计 ⊕ 开发 ⊕ 数据分析`，文字 `岗位界限已消失`
   - path 3: 双环融合动画 → 单环，文字 `决策 + 执行 = 合为一体`

4. 在 `AwakenNode` 中央节点处增加汇聚动画（三条路径到中央后融合闪光）。

**Step 2: 验证渲染**

Run: `npm run dev` → s6

**Step 3: Commit**

```bash
git add src/scenes/SceneAwaken.tsx
git commit -m "feat(s6): update awaken path labels and data per audio"
```

---

## Task 10: s7 SceneWhyTeam — 四重需要全换

**Files:**
- Modify: `src/scenes/SceneWhyTeam.tsx`

**改动说明：**

1. 更新 PHASES（2041帧 / 68.02s）：
   - P1: 0-510 帧 (0-17s) — 分担风险
   - P2: 510-1020 帧 (17-34s) — 稳定注意力
   - P3: 1020-1530 帧 (34-51s) — 积累信用
   - P4: 1530-2041 帧 (51-68s) — 实现更大价值

2. 替换 `reasons` 数据：

```typescript
const reasons: ReasonData[] = [
  {
    id: "risk",
    title: "分担风险",
    subtitle: "反脆弱：分散决策让小失败不断发生",
    icon: "🛡️",
    color: theme.colors.primary,
    position: { x: centerX - 220, y: centerY - 220 },
    delay: PHASES.phase1.start,
    rotation: -15,
  },
  {
    id: "attention",
    title: "稳定注意力",
    subtitle: "注意力恢复需 23min / 决策点 5→50/hr",
    icon: "🎯",
    color: theme.colors.secondary,
    position: { x: centerX + 220, y: centerY - 220 },
    delay: PHASES.phase2.start,
    rotation: 15,
  },
  {
    id: "credit",
    title: "积累信用",
    subtitle: "组织实体可长期承接托付",
    icon: "🏦",
    color: "#FFD700",
    position: { x: centerX - 220, y: centerY + 220 },
    delay: PHASES.phase3.start,
    rotation: -10,
  },
  {
    id: "value",
    title: "实现更大价值",
    subtitle: "复杂场景需同时判断 + 关系网络",
    icon: "🌐",
    color: theme.colors.accent,
    position: { x: centerX + 220, y: centerY + 220 },
    delay: PHASES.phase4.start,
    rotation: 10,
  },
];
```

3. 每块拼图下增加数据卡：
   - 分担风险：`+45% 五年存活率` `×1.8 获风投概率`
   - 稳定注意力：`注意力恢复 23min` `决策点 5→50/hr`
   - 积累信用：`组织实体可长期承接托付`
   - 实现更大价值：`复杂场景需同时判断 + 关系网络`

4. `CompleteMessage` 更新为：「四重需要，让超级个体选择聚合」。

**Step 2: 验证渲染**

Run: `npm run dev` → s7

**Step 3: Commit**

```bash
git add src/scenes/SceneWhyTeam.tsx
git commit -m "feat(s7): replace 4 team needs with risk/attention/credit/value"
```

---

## Task 11: s8 SceneForms — 增加 2×2 坐标轴 + 传统合伙

**Files:**
- Modify: `src/scenes/SceneForms.tsx`

**改动说明：**

1. 更新 PHASES（1595帧 / 53.16s）：
   - P1: 0-510 帧 (0-17s) — 2×2 矩阵框架
   - P2: 510-1260 帧 (17-42s) — 三种形态填入
   - P3: 1260-1595 帧 (42-53s) — 传统合伙

2. 更新 `FORMS` 描述：

```typescript
const FORMS: FormData[] = [
  {
    id: "form-radiation",
    title: "节点辐射型",
    subtitle: "Node Radiation",
    description: "中心超级个体 + AI辅助放大\n各节点独立工作",
  },
  {
    id: "form-network",
    title: "网络协作型",
    subtitle: "Network Collaboration",
    description: "无中心 + AI同步上下文\n对等协作模式",
  },
  {
    id: "form-aihub",
    title: "AI 中枢型",
    subtitle: "AI Hub",
    description: "AI全权编排\n所有人围绕 AI agent 工作",
  },
];
```

3. **新增 `AxisesOverlay` 组件**：在画面中央绘制十字坐标轴。
   - 横轴左端文字 `无AI协调`，右端 `AI协调`
   - 纵轴上端文字 `有中心节点`，下端 `无中心节点`
   - 4 个象限格子用虚线边框

4. **新增 `TraditionalPartnership` 组件**（P3）：
   - 左上象限（无中心+无AI协调）灰色虚线框
   - 文字 `传统合伙 / 开源模式`
   - 底部注释 `不算新物种`

5. 调整三种形态的象限位置到正确的 2×2 格子：
   - 节点辐射型 → 右上（有中心+无AI协调）—— 注：这里要注意，音频说的是「有中心节点 + AI只是辅助」，实际上节点辐射型没有AI协调，只有AI辅助放大，所以对应「有中心 + 无AI协调」即左上偏右
   - 网络协作型 → 左下（无中心+有AI协调）
   - AI中枢型 → 右下（有中心+有AI协调）

6. 更新 `SceneLabel` 为 `S8 · 三种形态`。

**Step 2: 验证渲染**

Run: `npm run dev` → s8

**Step 3: Commit**

```bash
git add src/scenes/SceneForms.tsx
git commit -m "feat(s8): add 2x2 matrix axes and traditional partnership cell"
```

---

## Task 12: s9 SceneCases — 运作机制 + 案例重写

**Files:**
- Modify: `src/scenes/SceneCases.tsx`

**改动说明：**

1. 更新 PHASES（3265帧 / 108.84s）：
   - P1: 0-600 帧 (0-20s) — 决策方式
   - P2: 600-1200 帧 (20-40s) — 协调规模
   - P3: 1200-1800 帧 (40-60s) — 技术栈+激励
   - P4: 1800-2700 帧 (60-90s) — 四公司卡片
   - P5: 2700-3265 帧 (90-108s) — 汇总

2. **新增 `DecisionDashboard` 组件**（P1）：4 种决策模式图标横排——👑一锤定音 / 🎯委托专家 / 🤝共识决策 / 🤖AI辅助。每项有标签文字，按提及时间 stagger 淡入。

3. **新增 `CoordinationScale` 组件**（P2）：三段渐变条 `5-50人→自治(绿)` / `50+→AI协调(蓝)` / `300+→IT设施(橙)`。使用 `interpolate` 逐段展开动画。

4. **新增 `TechIncentives` 组件**（P3）：3 个浮动徽章（World Model / Monorepo / AI Native Toolchain）+ 红色感叹号卡片 `「激励未解：10-100× 效率差异 → 薪酬如何体现？」`。

5. 替换 `CASES` 数据（P4）：

```typescript
const CASES: CaseData[] = [
  {
    name: "Codium",
    subtitle: "AI编码",
    keywords: ["自己挑任务", "整块交付", "AI时代任务越大越好"],
    description: "AI驱动的开发者协作平台\n90%+代码AI生成·一晚万行",
  },
  {
    name: "Kimi",
    subtitle: "月之暗面",
    keywords: ["≤500人", "无职级", "无KPI"],
    description: "刻意控制规模\n极致扁平的AI原生组织",
  },
  {
    name: "Block",
    subtitle: "美国",
    keywords: ["DRI制", "World Model", "2周→当天"],
    description: "金融服务AI化转型典范\n问题解决时间从两周压缩到当天",
  },
  {
    name: "Anthropic",
    subtitle: "AI安全",
    keywords: ["研究+工程合一", "无功能壁垒", "深度融合"],
    description: "研究人员和工程师完全合为一体\n打破传统功能壁垒",
  },
];
```

6. 公司卡片数量从 3 → 4，宽度调整 `cardWidth = Math.min(360, (width - 200) / 4)`。

7. **新增 `CaseSummary` 组件**（P5）：四张卡片同时发光脉冲，中央文字淡入 `「四种实践，同一种信念：AI时代组织要重新设计」`。

8. 更新 `SceneLabel` 为 `S9 · 运作+案例`。

**Step 2: 验证渲染**

Run: `npm run dev` → s9 → 确认 5 phase 过渡。

**Step 3: Commit**

```bash
git add src/scenes/SceneCases.tsx
git commit -m "feat(s9): add operations section + replace cases with Codium/Kimi/Block/Anthropic"
```

---

## Task 13: s10 SceneGardener — 扩展建议体系

**Files:**
- Modify: `src/scenes/SceneGardener.tsx`

**改动说明：**

1. 更新 PHASES（2024帧 / 67.46s）：
   - P1: 0-510 帧 (0-17s) — 园丁隐喻
   - P2: 510-1050 帧 (17-35s) — 给予三要素
   - P3: 1050-1560 帧 (35-52s) — 守护规则
   - P4: 1560-2024 帧 (52-67s) — 第一步

2. P1 保留 `DigitalTreeGrowth` + `Phase1Message`，副标题确认为 `好土壤+阳光+水分=让能力自然生长`。

3. **新增 `ThreeInputs` 组件**（P2）：三个能量输入从屏幕左侧飞入树根：
   - 🌍 完整问题
   - 🔧 必要工具
   - 📡 平台曝光
   每个输入以光流（SVG line + glow）连入树根，连线描画动画。

4. 替换 `ACTION_ITEMS`：

```typescript
const ACTION_ITEMS = [
  "允许试错",
  "≤15-20人 → 裂变",
  "减少中间环节",
  "协作不合 → 果断调整",
];
```

5. **新增 `FirstStepCard` 组件**（P4）：中央高亮大卡片：
   - 标题 `第一步`
   - 正文 `发现已在用AI的人 → 让成果被组织看到`
   - 底部引用 `管理者必须亲自使用AI —— 听汇报 ≠ 理解`
   - 卡片用 `theme.colors.primary` 边框 + glow pulse 动画。

6. 删除现有 `Phase2Title`、`Phase3Message`、`ClosingCTA`（收束内容移至 s11）。

**Step 2: 验证渲染**

Run: `npm run dev` → s10

**Step 3: Commit**

```bash
git add src/scenes/SceneGardener.tsx
git commit -m "feat(s10): expand gardener with 3 inputs + first step card"
```

---

## Task 14: s11 SceneClosing — 全新问题+收束场景

**Files:**
- Modify: `src/scenes/SceneClosing.tsx`（替换占位）

**改动说明：**

1. PHASES（2152帧 / 71.74s）：
   - P1: 0-600 帧 (0-20s) — 开放问题翻牌
   - P2: 600-1050 帧 (20-35s) — 终极选择
   - P3: 1050-1650 帧 (35-55s) — 总结回顾
   - P4: 1650-2152 帧 (55-71s) — CTA

2. **`QuestionCards` 组件**（P1）：4 张暗色卡片从屏幕底部翻入，每张翻转动画显示正面内容：
   - ❓ `15-20人：扩张还是裂变？→ 倾向裂变`
   - ❓ `AI = 基础设施？→ 信息透明是关键`
   - ❓ `10-100× 差异 → 薪酬怎么体现？→ 先做大蛋糕`
   - ❓ `非超级个体怎么办？→ 看身边榜样`
   翻牌用 CSS 3D `rotateY` + GSAP timeline。

3. **`UltimateChoice` 组件**（P2）：大字淡入 `当技术让你可以做任何事 → 你如何选择？`（`theme.fontSizes.title`）。停顿 1s 后，闪烁回答 `意义判断 —— 机器最难替代的能力`（`theme.colors.primary` + glow）。

4. **`FlashbackGrid` 组件**（P3）：3×3 九宫格小缩略图，每个格位展示一个场景的关键视觉元素（简化版），按原场景顺序快速闪烁（每格 30 帧 = 1s），中央叠加文字 `AI让个体能力极大放大 → 组织更灵活、扁平、有活力`。

5. **`ClosingCTA` 组件**（P4）：沿用原 SceneGardener 的 CTA 风格——
   - 大字 `开始培育你的超级团队`（`theme.fontSizes.display` 级）
   - 副标题 `从第一个人开始，让改变自然发生`
   - 装饰线 `width: 200` `linear-gradient(90deg, transparent, primary, transparent)`

6. 使用 `SceneBackground intensity={0.6} scanBeam={true}` + `SceneLabel "S11 · 问题+收束"`。

**Step 2: 验证编译+渲染**

Run: `npx tsc --noEmit && npm run dev` → s11

**Step 3: Commit**

```bash
git add src/scenes/SceneClosing.tsx
git commit -m "feat(s11): implement closing scene with questions/choice/flashback/CTA"
```

---

## Task 15: 全局验证 — Remotion Studio 完整播放

**Step 1: TypeScript 全量编译检查**

Run: `cd features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npx tsc --noEmit`

Expected: 无错误

**Step 2: Remotion Studio 全程播放**

Run: `npm run dev`

操作：
1. 从 s0 开始播放到 s11 结束
2. 确认每个场景的视觉内容与对应时段的字幕音频对齐
3. 特别关注场景切换时刻——视觉主题切换应与音频话题切换一致

**Step 3: 检查总帧数**

在浏览器控制台确认 `TOTAL_FRAMES = 21457`（715.22s × 30fps ≈ 21457）。

**Step 4: Commit**

如有微调：
```bash
git add -u
git commit -m "fix: minor timing adjustments after full playback verification"
```

---

## Task 16: 最终渲染

**Step 1: 渲染视频**

Run: `cd features/content-pipeline/tencent-super-team-mid-video/remotion-cyber && npm run render`

Expected: 输出 `production/videos/final_remotion.mp4`

**Step 2: 烧录字幕**

Run: `npm run burn-sub`

**Step 3: 播放验证**

手动播放最终视频，确认音画同步。

**Step 4: Commit**

```bash
git add -u
git commit -m "chore: render final aligned video with burned subtitles"
```