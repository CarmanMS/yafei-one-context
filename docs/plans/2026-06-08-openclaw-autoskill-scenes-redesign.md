# OpenClaw 双轨自进化 — 全场景重设计

**日期**：2026-06-08
**项目**：`features/content-pipeline/openclaw-self-improving-autoskill-mid-video/remotion/`
**目标**：修正画面层事实错误，全 10 场景重新设计 SVG 图形 + 文案 + 动画，交付 3 个可对比的 Remotion Composition。

## 背景

口播音频（WAV）和字幕（SRT）已定稿不可修改。审查发现画面层存在以下事实问题需通过重设计修正：

1. **SkillBank** 被呈现为 OpenClaw 社区组件 → 实为 AutoSkill 论文代码目录名
2. **"合入 knowledge"** → 仓内 spec 明确「不自动合入」，仅输出建议
3. **集成图** 将 SkillBank 与 ClawHub 并列 → 误导观众认为同级组件

画面层展示事实正确版本，不加标注、不跟随口播错误。

## 内容层设计（三版共享）

| 场景 | 视觉隐喻 | 文案要点 |
|------|----------|----------|
| s00 封面 | 双轨同心环 | OpenClaw 双轨自进化 / Self-Improving + AutoSkill |
| s01 痛点 | 断裂链条（4 节点 2 断线闪红） | 程序性记忆断裂 / 每次从零 |
| s02 双轨总览 | 上下双层轨道（铁轨意象） | 上层轻轨 Self-Improving / 下层重载 AutoSkill |
| s03 Self-Improving | 笔记本翻页隐喻 | 失败→写入 LEARNINGS→注入上下文→promote |
| s04 AutoSkill | 环形流水线（首尾相连） | 提取→维护→检索(BM25+语义)→执行 |
| s05 三方对比 | 三列光谱（色彩分重量级） | SkillClaw(AMAP-ML 离线蒸馏) / SkillOS(RL 治理) / OpenClaw(Markdown+hooks) |
| s06 集成 | 中心辐射 4 节点 | ClawHub(安装) / hooks(触发) / AGENTS.md(注入) / MCP(外部能力) |
| s07 one-context | 环形闭环 + 人工决策门（虚线） | 执行→记录→评估→**输出改进建议（人审）** |
| s08 适用场景 | 仪表盘（绿灯/红灯/起步路径） | 高频重复=绿 / 一次性=红 / 先 Self-Improving 再 AutoSkill |
| s09 收尾 | 文字聚合 | 双轨拆解完成 / 关注引导 |

### 事实修正明细

| 原画面 | 修正为 | 依据 |
|--------|--------|------|
| IntegrationHub 节点 "SkillBank" | 删除，替换为 "AGENTS.md（注入）" | SkillBank 非 OpenClaw 组件 |
| EvolutionLoop "合入 knowledge" | "输出改进建议（人审）" | spec 非目标第一条 |
| SceneTopic integrate subtitle "ClawHub · SkillBank · hooks · MCP" | "ClawHub · hooks · AGENTS.md · MCP" | 同上 |
| ThreeWayCompare SkillClaw 行 | 注明 "AMAP-ML" | 非「阿里」主体 |

## 动画策略（三版）

### 版本 A — 重点动画版

- s02 / s04 / s06：Anime.js timeline（逐步构建、描线、节点飞入）
- 其余 7 场：Remotion spring（标题弹入 + SVG 整体 fade）

### 版本 B — 全场轻动画版

- 所有 10 场：Remotion spring + 子元素 stagger（每节点延迟 8-12 帧 opacity + translateY）
- 零额外依赖

### 版本 C — 全场 Anime.js Timeline 版

| 场景 | 动画概要 |
|------|----------|
| s00 | 双环从点扩张为圆，文字从中心弹出 |
| s01 | 链条节点逐个出现，断裂处闪红+抖动 |
| s02 | 双轨从一条线分裂为上下两层，元素滑入各自轨道 |
| s03 | 笔记本翻页：每步像翻一页，文字手写描线 |
| s04 | 环形流水线旋转构建，箭头描线，节点脉冲 |
| s05 | 三列从底部升起（柱状图），标签 stagger 弹入 |
| s06 | 中心扩张→连线辐射→节点着陆 |
| s07 | 环形节点逐个亮起，「人审」门虚线闪烁 |
| s08 | 仪表盘灯逐个亮绿/亮红，起步路径描线 |
| s09 | 文字从散落聚合为完整句子 |

## 项目结构

```
remotion/src/
├── scenes/
│   ├── svg/
│   │   └── Diagrams.tsx              ← 共享：10 个修正后 SVG 组件
│   ├── variants/
│   │   ├── A/
│   │   │   ├── SceneTopicA.tsx       ← 3 Anime + 7 Spring
│   │   │   └── anime-timelines.ts
│   │   ├── B/
│   │   │   └── SceneTopicB.tsx       ← Spring stagger wrapper
│   │   └── C/
│   │       ├── SceneTopicC.tsx       ← 全场 Anime
│   │       └── anime-timelines.ts
│   ├── SceneCover.tsx                ← 共享
│   └── SceneOutro.tsx                ← 共享
├── shared/animations/anime/          ← 已有 hook 复用
└── Root.tsx                          ← 3 Composition: VersionA / VersionB / VersionC
```

## 交付物

- Remotion Studio 可预览的前端代码
- 浏览器 `npx remotion studio` 切换 VersionA / VersionB / VersionC 对比
- 不出片、不烧字幕

## 约束

- audioConfig.ts 不变（时长锁定）
- WAV / SRT 不动
- 字号遵循 SKILL.md 硬约束（正文≥42px，SVG text≥28px）
- 动画前 20% 构建、中 60% 展示、末 20% 微动效
