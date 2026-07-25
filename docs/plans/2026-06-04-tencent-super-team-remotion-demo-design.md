# 腾讯超级团队中视频 Remotion 演示设计

> **日期**: 2026-06-04
> **Feature**: `content-pipeline/tencent-super-team-mid-video`
> **Skill**: `skills/remotion-pipelines/`
> **状态**: 已确认

## 概述

为 `tencent-super-team-mid-video` 特性使用 `remotion-pipelines` 技能制作三版可视化风格演示（仅 Remotion Studio 预览，不渲染最终 MP4）。

### 关键决策

| 维度 | 决策 |
|------|------|
| 视觉风格 | 三版：Cyber（科技简约+数据可视化）、Biz（商务专业+图表驱动）、Sketch（手绘/白板风） |
| 场景范围 | 每版全部 9 个场景 (S0-S8) |
| 动画复杂度 | 重度动画（四轨动画系统全用） |
| 色彩体系 | 复用 remotion-pipelines `shared/colors.ts` |
| 输出 | 仅 Remotion Studio 预览 |
| 代码架构 | 三套独立项目 |
| 实施方案 | 场景优先（Scene-first），按 S0→S8 逐场景推进三版 |

## 项目结构

```
features/content-pipeline/tencent-super-team-mid-video/
├── remotion-cyber/          # 科技简约 + 数据可视化
│   ├── package.json
│   ├── remotion.config.ts
│   ├── src/
│   │   ├── index.ts
│   │   ├── Root.tsx
│   │   ├── audioConfig.ts
│   │   ├── style-guide.ts
│   │   ├── scenes/
│   │   │   ├── SceneCover.tsx     (S0)
│   │   │   ├── SceneGap.tsx       (S1)
│   │   │   ├── SceneEvolution.tsx (S2)
│   │   │   ├── SceneFourTraits.tsx(S3)
│   │   │   ├── SceneAwaken.tsx    (S4)
│   │   │   ├── SceneWhyTeam.tsx   (S5)
│   │   │   ├── SceneForms.tsx     (S6)
│   │   │   ├── SceneCases.tsx     (S7)
│   │   │   └── SceneGardener.tsx  (S8)
│   │   └── shared/               # 从 remotion-pipelines 复制
│   │       ├── colors.ts
│   │       ├── typography.ts
│   │       ├── SceneBackground.tsx
│   │       ├── layouts/
│   │       └── animations/
│   └── public/audio/
├── remotion-biz/            # 商务专业 + 图表驱动（同结构）
├── remotion-sketch/         # 手绘/白板风（同结构）
├── production/              # 共享内容素材（已存在）
│   ├── media/voiceover.wav
│   ├── subtitles/sub.srt
│   └── timing/wav-durations.json
└── spec.md
```

三套项目共享 `production/` 目录下的音频/字幕/时间数据，通过相对路径引用。

## 三种风格视觉语言

### Cyber（科技简约 + 数据可视化）

| 维度 | 规范 |
|------|------|
| 背景 | `SceneBackground` 的 `circuit` 或 `particles` 模式，深色（#0a0a1a → #1a1a3a 渐变） |
| 主色 | 霓虹青 `#00f5d4`，强调紫 `#b388ff`，警示红 `#ff4757` |
| 数据图 | SVG 折线/柱状图，发光描边 + 数据流动粒子 |
| 卡片 | 圆角 4px，玻璃态毛玻璃（backdrop-blur），边框发光 |
| 文字 | 等宽标题（JetBrains Mono / Space Grotesk），正文 Inter |
| 转场 | 数字溶解（像素化过渡）、扫描线扫过 |
| 动画特效 | 打字机效果、数据流粒子沿路径运动、节点脉冲发光 |
| 动画轨道 | GSAP（主）+ Anime.js（辅）+ Remotion 原生（转场） |

### Biz（商务专业 + 图表驱动）

| 维度 | 规范 |
|------|------|
| 背景 | 浅色渐变（#f8fafc → #e2e8f0），微妙几何网格线 |
| 主色 | 深蓝 `#1e40af`，辅助金 `#d97706`，灰色系分层 |
| 数据图 | 扁平条形图/饼图/环形图，无发光，阴影分层 |
| 卡片 | 圆角 12px，白底 + 精致阴影，左侧色条标记 |
| 文字 | 标题 Source Serif / Noto Serif SC，正文 Noto Sans SC |
| 转场 | 淡入淡出 + 滑动，平滑过渡 |
| 动画特效 | 数字滚动计数、图表从 0% 增长到目标值、列表逐项展开 |
| 动画轨道 | Remotion 原生（主）+ GSAP（数据动画） |

### Sketch（手绘/白板）

| 维度 | 规范 |
|------|------|
| 背景 | 仿白板质感（#fafafa + 微噪点），带淡淡网格线 |
| 主色 | 马克笔色系——深灰 `#2d3436`、蓝笔 `#0984e3`、红笔 `#d63031`、绿笔 `#00b894` |
| 数据图 | 手绘风格 SVG（roughjs 或手绘路径），不对称线条 |
| 卡片 | 模拟便利贴/虚线框，轻微旋转（-2°~2°） |
| 文字 | 手写体（Ma Shan Zheng / Caveat），非关键数据用"手写" |
| 转场 | 翻页/擦除效果，模拟白板擦除 |
| 动画特效 | strokeDashoffset 路径绘制动画、逐笔"画出"效果、元素弹跳入场 |
| 动画轨道 | Remotion 原生（位移/缩放）+ Lottie（手绘笔触/翻页）+ strokeDashoffset |

### style-guide.ts 结构

每个项目包含一个 `style-guide.ts`，作为视觉宪法：

```typescript
export const theme = {
  name: 'cyber' | 'biz' | 'sketch',
  colors: { primary, secondary, accent, warning, bg, bgSecondary, text, textMuted },
  typography: { heading, body, caption, mono },
  spacing: { xs, sm, md, lg, xl, section },
  shapes: { cardRadius, cardBorder, cardShadow, cardBg },
  animations: { transitionDuration, easing, stagger, glow, pulse },
  backgrounds: { default, variant },
} as const;
```

## 九个场景视觉隐喻

### S0 封面（14.56s）— 核心：组织竞争力公式

> 组织竞争力 = 人才密度 × AI杠杆 / 组织摩擦

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 公式在矩阵雨中浮现，数据粒子汇成公式字符 | GSAP 粒子汇聚 → 公式从模糊到清晰 → 标题 typewriter 出场 |
| Biz | 公式从底部逐行上升，如幻灯片演示 | Remotion spring 入场 → 数字滚动到目标值 → 副标题 fade-in |
| Sketch | 手写公式从左到右"写出" | strokeDashoffset 路径绘制 → 完成后墨迹扩散 → 标题手写体入场 |

### S1 AI 采用鸿沟（123.64s）— 核心：88% vs 1%

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 两段数据柱状图（发光条），88% 柱极高，1% 柱极低，鸿沟区域闪烁红光 | 条形 GSAP 从 0 增长，鸿沟粒子流断裂，数字脉冲跳动 |
| Biz | 水平对比条形图，蓝色 vs 金色，差距标注 | 平滑增长动画，标注线逐条出现，footnote 淡入 |
| Sketch | 两块"便利贴"柱图，1% 那条贴了"?"标签 | 手绘条形"画出来"，问号弹跳出现，分数线手写 |

### S2 演化链（52.78s）— 核心：个体 → 工具增强 → 超级个体

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 节点网络图，节点依次亮起绿色脉冲，连线发光 | GSAP 路径动画：节点 1→2→3 依次 pulse，连线粒子流 |
| Biz | 三步流程箭头图，每步有图标和标签 | 箭头从左到右渐进出现，图标旋转入场，标签 fade-in |
| Sketch | 手绘箭头链，每步是简笔画人形 | strokeDashoffset 绘制箭头，人形简笔画逐个画出 |

### S3 四特征（103.88s）— 核心：四象限/四核模型

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 四象限雷达图/能量核心，每个象限有数据流 | 雷达图线条逐段绘制 + glow，各象限数据粒子旋入，中心脉冲 |
| Biz | 2×2 矩阵卡片，每格有图标+关键词+描述 | 卡片依次从中心展开，图标 bounce 入场，描述逐字 fade |
| Sketch | 手绘四格圆，每个圆内简笔画 | 圆形 path 绘制，内部分步"画"出来，箭头连接 |

### S4 觉醒路径（53.28s）— 核心：开发者/非工程师/创始人

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 三条发光路径（电路板走线），汇聚到中心"觉醒"节点 | 路径粒子流动画（Anime.js），汇聚节点爆炸光芒 |
| Biz | 三栏并排时间线，各有里程碑标记 | 时间线从上到下展开，里程碑图标 pop，连线动画 |
| Sketch | 三条手绘蜿蜒路，终点是一盏灯 | 路径逐步绘制，灯泡最后"点亮"发光 |

### S5 为何需要团队（66.52s）— 核心：四重需要

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 四块拼图/四节点集群，缺失一环系统脆弱 | 拼图块旋转飞入位置，缺口闪烁红光警告，完整后绿色锁定 |
| Biz | 四个圆形图标围绕中心"团队"标签 | 圆形 scale 入场，连线展开，中心标签最后出现 |
| Sketch | 四个手绘积木堆叠，缺一块就倒 | 积木逐个摆放（shake+drop），缺的那块红色手绘框标注 |

### S6 三种团队形态（111.80s）— 核心：节点辐射/网络协作/AI中枢

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 节点网络图 ×3：辐射型→网状→AI中枢，节点间实时数据流 | GSAP 形态1→2→3 变形动画，节点重排，连线溶解重连 |
| Biz | 三个组织架构图（树形→矩阵→星形） | 架构图渐显，节点滑动到位，连线绘制，形态间虚线箭头 |
| Sketch | 三个手绘组织图，用不同颜色笔 | 节点逐个画出，连线手绘，形态切换时"翻页" |

### S7 案例（51.82s）— 核心：CodeBuddy / Kimi / Block

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 三张全息卡片，悬浮在数据空间 | 卡片 3D rotate 入场，hover glow 效果，关键词高亮扫描 |
| Biz | 三张商务卡片，白底+色条+关键数据 | 卡片从底部 slide-up，数据计数器滚动，成功指标绿色箭头 |
| Sketch | 三张便利贴，带图钉和手写标注 | 便利贴"拍"上去（shake+drop），手写标注逐步写上 |

### S8 园丁收束（137.37s）— 核心：园丁隐喻 + 行动清单

| 风格 | 视觉隐喻 | 动画 |
|------|---------|------|
| Cyber | 数字花园——绿色粒子从土壤中生长为树形网络 | GSAP 粒子→树生长动画，阳光光束扫描，行动清单逐行 typewriter |
| Biz | 渐变色带+行动清单图标列表 | 色带展开，行动项逐条 slide-in + 图标，CTA 淡入放大 |
| Sketch | 手绘花盆→植物生长→花园 | strokeDashoffset 花盆+枝叶绘制，行动项便利贴逐个贴上 |

## 动画系统架构

### 四轨动画分配

| 动画轨道 | Cyber | Biz | Sketch |
|---------|-------|-----|--------|
| Remotion 原生 | 转场、fade、spring | 主要动画层 | 简单位移/缩放 |
| Anime.js | 节点脉冲、数据流粒子 | — | — |
| GSAP | 粒子汇聚、树生长、形态变形 | 数字滚动、图表增长 | — |
| Lottie | — | — | 手绘笔触效果、翻页 |

### audioConfig.ts

三套项目共用时序数据（策略 A：完整 WAV）：

```typescript
const sceneDurations = [14.56, 123.64, 52.78, 103.88, 53.28, 66.52, 111.8, 51.82, 137.37];
```

音频文件通过相对路径引用 `production/media/voiceover.wav`。

### 场景组件标准接口

```typescript
interface SceneProps {
  sceneIndex: number;
  durationInFrames: number;
}
```

每个场景组件通过 `useTheme()` 从 `style-guide.ts` 获取当前风格参数，确保视觉一致性。

## 执行计划

### Phase 0: 项目初始化

1. 对三个风格分别运行 `node cli.mjs init`
2. 建立各风格的 `style-guide.ts`
3. 配置 `audioConfig.ts`（共用 wav-durations.json 数据）
4. 验证 Remotion Studio 预览可用

### Phase 1-9: 场景优先推进

按 S0→S8 顺序，每场景三版同步完成：

| 阶段 | 场景 | 时长 | 核心视觉挑战 |
|------|------|------|-------------|
| Phase 1 | S0 封面 | 14.56s | 公式动画（三种风格差异化最大） |
| Phase 2 | S1 AI鸿沟 | 123.64s | 对比数据图（最长场景） |
| Phase 3 | S2 演化链 | 52.78s | 流程/路径动画 |
| Phase 4 | S3 四特征 | 103.88s | 四象限/矩阵布局 |
| Phase 5 | S4 觉醒路径 | 53.28s | 三路径汇聚动画 |
| Phase 6 | S5 为何需要团队 | 66.52s | 拼图/集群动画 |
| Phase 7 | S6 三种形态 | 111.80s | 网络拓扑变形（最复杂动画） |
| Phase 8 | S7 案例 | 51.82s | 卡片组件 |
| Phase 9 | S8 园丁收束 | 137.37s | 生长动画 + 清单 |

### 每场景完成标准

- ✅ Remotion Studio 可预览，音频同步
- ✅ 动画流畅无卡顿（30fps）
- ✅ 视觉隐喻清晰，文字精简为关键词
- ✅ 画布利用率 ≥ 70%
- ✅ 引用 style-guide.ts，无硬编码颜色/字体

## 风险与约束

1. **手绘风格 SVG 工作量**：Sketch 风格的 roughjs 手绘路径需要大量自定义 SVG，可考虑用 Lottie 预制动画降低复杂度
2. **三版项目维护成本**：场景逻辑修改需要同步三处，建议用 diff 检查确保结构一致
3. **音频文件路径**：三套项目通过相对路径共享 `production/media/voiceover.wav`，需确保 Remotion 能正确解析
4. **字体加载**：三种风格各需不同字体（等宽/衬里/手写），需确认 Google Fonts 或本地字体可用