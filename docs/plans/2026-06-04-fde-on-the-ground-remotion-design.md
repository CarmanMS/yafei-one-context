# FDE 驻场工程师中视频 — Remotion 场景设计

> **Feature**: `fde-on-the-ground-mid-video`
> **Skill**: `remotion-pipelines`
> **日期**: 2026-06-04
> **状态**: 已批准

---

## 1. 目标

为 `features/content-pipeline/fde-on-the-ground-mid-video` 制作 Remotion 场景，渲染 7 场口播中视频（~6:30），交付 `production/videos/final_remotion_sub.mp4`。

## 2. 约束

| 项 | 值 |
|----|-----|
| 分辨率 | 1920×1080 |
| 帧率 | 30fps |
| 音频 | `media/voiceover.wav`（389.52s） |
| 字幕 | `subtitles/sub.srt`（173 条） |
| TTS 路由 | `volc-podcast-tts` action=0, authority=wav_srt |
| 场景数 | 7（s0–s6） |
| 口播来源 | `00-podcast-source.md` |

## 3. 技术方案：方案 B — 共享基座 + 工业主题层

复用 `remotion-pipelines` 共享层（布局/动画/hooks/SceneBackground），在此基础上：

- 覆写 `colors.ts` / `typography.ts` 为工业风格
- 场景组件全新设计
- 全场景 Lottie 主动画 + GSAP/Anime.js 文字编排

## 4. 视觉风格：工业沉稳风

### 4.1 色彩系统 — `colors.ts`

| Token | 值 | 用途 |
|-------|-----|------|
| `bg` | `#0B1120` | 深蓝黑底 |
| `bgElevated` | `#131B2E` | 卡片/面板抬升层 |
| `text` | `#E8ECF4` | 主文字（冷白） |
| `muted` | `#8892A4` | 次要文字 |
| `accent` | `#4A9EFF` | 主强调 — 钢蓝（工程感） |
| `accentDim` | `rgba(74,158,255,0.15)` | 钢蓝淡底 |
| `accentWarm` | `#F0A050` | 暖强调 — 金属铜（数据高亮） |
| `accentWarmDim` | `rgba(240,160,80,0.15)` | 金属铜淡底 |
| `success` | `#3DDC84` | 正向指标绿 |
| `danger` | `#FF5252` | 负向指标红 |
| `steelGradient` | `linear-gradient(135deg, #1A2340, #2A3A5C)` | 面板渐变 |
| `metallic` | `linear-gradient(90deg, #6B7B99, #AAB4C8, #6B7B99)` | 金属字 |

### 4.2 字体系统 — `typography.ts`

| Token | 值 | 用途 |
|-------|-----|------|
| `chinese` | `"Noto Sans SC", sans-serif` | 中文正文（无衬线） |
| `english` | `"Inter", sans-serif` | 英文/数字（几何工程字体） |
| `mono` | `"JetBrains Mono", monospace` | 代码/数据 |

**与姊妹篇差异**：Noto Serif SC → Noto Sans SC，Playfair Display → Inter。

### 4.3 背景

复用 `SceneBackground` 框架，微调粒子色为钢蓝色系。各场景 intensity：
- s0 封面：1.0（六边形网格）
- s1 定义：0.5（扫描光柱）
- s2 一周：0.4（电路痕迹）
- s3 Deere：0.3（数据流）
- s4 Travelers：0.4（粒子连线）
- s5 Morgan：0.3（轨道环）
- s6 对比：0.2（六边形网格）

## 5. Lottie 集成策略

### 5.1 项目已有基础设施

| 来源 | 能力 |
|------|------|
| `remotion-pipelines` shared | `<Lottie animationData />` 组件 + `useLottieSeek` hook |
| `claude-remotion-editor` 参考 | Lottie 生产规范（规则 53-57）、`public/lottie/` 素材库、HF seek 模式 |
| 依赖 | `@remotion/lottie` + `lottie-web` |

### 5.2 两种路径选择

| 场景 | 路径 | 理由 |
|------|------|------|
| s0/s2/s4（复杂多层动画） | `useLottieSeek` | 需要分段播放（playSegments）、子图层控制 |
| s1/s3/s5/s6（标准播放） | `<Lottie animationData />` | 帧驱动直接播放，更简单 |

### 5.3 Lottie 文件存放

```
remotion/public/lottie/
├── cover-gate.json          # s0 工厂门框
├── define-engine.json       # s1 引擎齿轮
├── week-cycle.json          # s2 五步循环引擎
├── deere-funnel.json        # s3 精准喷射漏斗
├── travelers-map.json       # s4 地图 Rollout
├── morgan-timeline.json     # s5 信任建设时间线
└── compare-dashboard.json   # s6 对比仪表盘背景微动效
```

### 5.4 Lottie 生产规范（来自 claude-remotion-editor）

- 使用 `staticFile("lottie/xxx.json")` 或 `import xxxJson from "../../public/lottie/xxx.json"` 导入
- 禁用 `loop`（Remotion 帧驱动不需要循环）
- `autoplay: false`（Remotion 控制播放）
- 确保 Lottie JSON 中无远程资源引用（图片/字体 path）
- 渲染前用 `lottie-web` 的 `AnimationItem.totalFrames` 验证帧数与场景时长对齐
- 大型 JSON（>500KB）考虑用 `delayRender` + `fetch` 延迟加载

### 5.5 各场景 Lottie 动画设计

| 场景 | Lottie 主动画 | 播放方式 | 文字/数据层 |
|------|-------------|---------|------------|
| **s0 封面·29s** | 工厂门框从中央裂开，钢蓝光芒泄漏，六边形粒子飞散 | `useLottieSeek` 全程播放 | 主标题逐字 reveal + 副标题淡入 |
| **s1 定义·68s** | 左侧售前 PPT→❌ 覆盖，右侧引擎齿轮旋转→流水线节点逐亮 | `useLottieSeek` 分段（0-30s 售前侧，30-68s FDE 侧） | 底部关键词由 GSAP 编排 |
| **s2 一周·96s** | 五步循环引擎：齿轮组旋转，每阶段闪光+连线流转，Discovery 子图下拉 | `useLottieSeek` 分段（intro/流程/Discovery） | 阶段标签 + 子图注释代码驱动 |
| **s3 Deere·80s** | 漏斗三层流动（专家→Evals→推荐），喷射粒子 | `<Lottie />` 循环播放（loop=false, Remotion 帧驱动） | 左右数据卡 GSAP 弹出 |
| **s4 Travelers·54s** | 地图 8 点亮起→涟漪扩散→全图填充，脉冲波纹 | `useLottieSeek` 分段 | 右侧数据卡 GSAP 弹出 |
| **s5 Morgan·44s** | 时间线 4 节点逐亮，连线描线流动，✅ 对勾弹出，⏳ 脉冲 | `useLottieSeek` 分段 | 底部来源标注代码驱动 |
| **s6 对比·18s** | 仪表盘背景微光流动（轻量 Lottie） | `<Lottie />` 全程播放 | 四列对比表由 GSAP stagger 驱动 |

## 6. 7 场景视觉隐喻详案

### s0 — SceneCover（29.06s，帧 0–871）

**隐喻：车间大门打开**

- Lottie 主动画：工厂门框从中央裂开，钢蓝光芒泄漏，六边形粒子飞散
- 主标题「FDE 驻场工程师到底在干嘛」Anime.js 逐字描线 + 填色
- 副标题「Forward Deployed Engineer · On the Ground」淡入
- 背景：SceneBackground intensity=1.0 + 六边形网格
- 关键动画帧：帧 0–300 门框裂开，帧 200–500 光芒泄漏，帧 400+ 粒子飞散，帧 300+ 标题 reveal

### s1 — SceneDefine（68.38s，帧 872–2922）

**隐喻：不是售前，是驻场引擎**

- Lottie 主动画（useLottieSeek 分段）：
  - 0–30s：左侧售前 PPT 图标 → 红色 ❌ 覆盖
  - 30–68s：右侧引擎齿轮旋转 → 流水线节点逐亮
- 底部关键词条 GSAP stagger：`驻场 → 大模型/智能体 → 可运行工作流 → 可量化评估`
- 背景：SceneBackground intensity=0.5 + 扫描光柱
- 口播锚点：SRT #11「什么是 FDE · 不是售前」

### s2 — SceneWeek（95.62s，帧 2923–5791）⭐ 最长场景

**隐喻：五步循环引擎**

- Lottie 主动画（useLottieSeek 三段触发）：
  - Intro（0–20s）：中央齿轮组启动
  - 流程（20–55s）：五阶段横向流转 — `发现 → 原型 → 合规联调 → 上线 → 迭代`
  - Discovery（55–96s）：从「发现」节点下拉展开子图
- 每阶段图标：放大镜、齿轮/扳手、盾牌、火箭、循环箭头
- Discovery 子图：访谈 → 调研权限 → 流程图/优先级矩阵/价值热力图
- 背景：SceneBackground intensity=0.4 + 电路痕迹
- 口播锚点：SRT #38「典型一周」

### s3 — SceneDeere（79.80s，帧 5792–8185）

**隐喻：精准喷射漏斗**

- Lottie 主动画：三层漏斗流动（专家审核 → 自定义 Evals → AI 推荐）+ 喷射粒子
- 数据卡片 GSAP 弹出：
  - 左：`-70%` 化学用量（success 绿）
  - 右：`6×` 客户互动（accentWarm 铜色）
- 底部：自然语言交互示意（对话气泡 → 设备图标）
- 背景：SceneBackground intensity=0.3 + 数据流
- 口播锚点：SRT #81「John Deere 案例」

### s4 — SceneTravelers（54.32s，帧 8186–9815）

**隐喻：地图 Rollout 扩散**

- Lottie 主动画（useLottieSeek 分段）：
  - 0–20s：8 个州亮起（蓝色小圆点弹簧入场）
  - 20–40s：涟漪扩散
  - 40–54s：全地图填充 accent 色
- 右侧数据卡：`150万+ /年理赔`、`$230亿+ 赔付`、`85-90% 采纳率`
- 底部标签：`AI Claim Assistant · Realtime API`
- 背景：SceneBackground intensity=0.4 + 粒子连线
- 口播锚点：SRT #118「Travelers 车险」

### s5 — SceneMorgan（43.86s，帧 9816–11131）

**隐喻：信任建设时间线**

- Lottie 主动画（useLottieSeek 分段）：
  - 节点 1：研报 RAG ✅（钢蓝高亮）
  - 节点 2：Evals + 护栏（灰→亮）
  - 节点 3：数月试点 ⏳（金属铜色脉冲）
  - 节点 4：98% 采纳 ✅（success 绿 + 对勾）
- 时间线连线 Anime.js 描线
- 底部标注：`公开访谈整理（Colin Jarvis）· 非 OpenAI 案例页`
- 背景：SceneBackground intensity=0.3 + 轨道环
- 口播锚点：SRT #146「Morgan Stanley 模式」

### s6 — SceneCompare（18.48s，帧 11132–11685）⭐ 最短场景

**隐喻：四列对比仪表盘**

- Lottie 主动画（轻量）：背景微光流动 + 网格线呼吸
- 四列对比表纯 GSAP stagger 驱动：
  - 列：FDE / AI Engineer / 咨询 / SE
  - 行：重心、交付物、成功标准、驻场
- FDE 列整列钢蓝高亮
- 入场：列从左到右 80ms 间隔
- 背景：SceneBackground intensity=0.2 + 六边形网格
- 口播锚点：SRT #165「角色对比」

## 7. 技术架构

### 7.1 目录结构

```
remotion/
├── package.json
├── remotion.config.ts
├── tsconfig.json
├── public/
│   ├── audio/
│   │   └── voiceover.wav
│   └── lottie/
│       ├── cover-gate.json
│       ├── define-engine.json
│       ├── week-cycle.json
│       ├── deere-funnel.json
│       ├── travelers-map.json
│       ├── morgan-timeline.json
│       └── compare-dashboard.json
├── scripts/
│   ├── burn-subtitles.mjs
│   ├── generate-audioconfig.mjs
│   └── ensure-shared-browser.mjs
└── src/
    ├── index.ts
    ├── Root.tsx
    ├── audioConfig.ts              # 7 场配置（单一数据源）
    ├── hooks/
    │   └── useCurrentSceneIndex.ts
    ├── scenes/
    │   ├── index.tsx               # SceneRouter
    │   ├── SceneCover.tsx          # s0
    │   ├── SceneDefine.tsx         # s1
    │   ├── SceneWeek.tsx           # s2
    │   ├── SceneDeere.tsx          # s3
    │   ├── SceneTravelers.tsx      # s4
    │   ├── SceneMorgan.tsx         # s5
    │   ├── SceneCompare.tsx        # s6
    │   └── svg/                    # 场景专用 SVG 组件
    │       ├── FactoryGate.tsx
    │       ├── EngineGear.tsx
    │       ├── PipelineFlow.tsx
    │       ├── FunnelDiagram.tsx
    │       ├── USMap.tsx
    │       ├── TrustTimeline.tsx
    │       └── DashboardGrid.tsx
    └── shared/                     # 从 remotion-pipelines/shared 复制 + 覆写
        ├── index.ts
        ├── colors.ts              # 工业色彩系统
        ├── typography.ts          # 无衬线字体系统
        ├── SceneBackground.tsx    # 微调粒子色
        ├── animations/
        │   ├── gsap.ts
        │   ├── useGSAPTimeline.ts
        │   ├── anime.ts
        │   └── lottie/
        │       ├── index.ts
        │       └── useLottieSeek.ts
        └── layouts/
            ├── FullBleedTitle.tsx
            └── SplitLayout.tsx
```

### 7.2 audioConfig.ts

```typescript
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

// TOTAL = 11686 帧 @ 30fps = 389.53s
```

### 7.3 SceneRouter 模式

switch-based routing + 单音频文件模式（与姊妹篇一致）。

### 7.4 字号约束

| 元素 | 最小字号 | 备注 |
|------|---------|------|
| 封面主标题 | ≥120px（推荐 140-160px） | Anime.js 逐字描线 |
| 卡片标题 | ≥52px | 标签/名词 |
| 正文/路径 | ≥42px | 中文字体 |
| SVG `<text>` | ≥28px（3字+ ≥32px） | 图内标注 |

### 7.5 渲染管线

```bash
npm run dev          # Remotion Studio 预览
npm run render       # → final_remotion.mp4（无字幕）
npm run burn-sub     # → final_remotion_sub.mp4（最终交付）
npm run render:full  # render + burn-sub 串联
```

## 8. 依赖

```json
{
  "dependencies": {
    "@remotion/lottie": "^4.0.0",
    "lottie-web": "^5.12.0",
    "animejs": "^4.4.1",
    "gsap": "^3.15.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "remotion": "^4.0.0"
  }
}
```

字体加载：`@remotion/google-fonts` 预加载 Inter + Noto Sans SC + JetBrains Mono。

## 9. 实施计划

| 阶段 | 内容 | 预估 |
|------|------|------|
| **P0 基座** | CLI init → 覆写 colors/typography → audioConfig → SceneRouter → 音频验证 | 0.5 天 |
| **P1 封面** | SceneCover（Lottie 门框 + Anime.js 逐字）— 确立视觉基调 | 2 天 |
| **P2 定义场景** | SceneDefine（Lottie 引擎 + GSAP 双卡片）| 2 天 |
| **P3 最长场景** | SceneWeek（Lottie 五步循环 + Discovery 子图）— 最复杂 | 2.5 天 |
| **P4 三案例** | SceneDeere + SceneTravelers + SceneMorgan — 并行开发 | 3 天 |
| **P5 对比表** | SceneCompare（轻量 Lottie + GSAP stagger）| 1 天 |
| **P6 渲染交付** | render:full → 字幕烧录 → 成片自检 → 更新 publish-kit | 0.5 天 |

**总预估**：~11.5 天

## 10. 风险与缓解

| 风险 | 概率 | 缓解 |
|------|------|------|
| Lottie JSON 与场景时长不对齐 | 中 | 用 `AnimationItem.totalFrames` 验证，配合 `playbackRate` 调速 |
| GSAP+Lottie 双 timeline 帧偏移 | 中 | 每场景独立测试，Lottie 进度用 `useLottieSeek` 精确 seek |
| Lottie JSON 含远程资源导致渲染失败 | 低 | 渲染前扫描 JSON 中 `p`/`u` 字段，确保无外部 URL |
| 大型 Lottie JSON（>500KB）影响启动 | 低 | 用 `delayRender` + `fetch` 延迟加载 |
| SceneWeek 96s 过长，动画分段困难 | 中 | 拆分为 3 个子时间线（Intro/流程/Discovery），`interpolate()` 切换 |
| 字体加载缺失导致 fallback | 中 | `@remotion/google-fonts` 预加载 |

## 11. 不做（YAGNI）

- ❌ Lottie 创作工具/AE 工作流（Lottie JSON 由外部来源提供）
- ❌ 响应式（1920×1080 固定）
- ❌ s7/s8 场景（口播无内容）
- ❌ 多语言/多音频版本
- ❌ D3.js 数据可视化（SVG 硬编码确定性渲染）