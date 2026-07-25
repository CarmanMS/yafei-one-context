# Postgres AI Agent Mid-Video · 3 套 Remotion 预览 Demo

**Feature**：`features/content-pipeline/postgres-ai-agent-default-db-mid-video/`
**Skill**：`skills/remotion-pipelines/`
**日期**：2026-06-04
**作者**：主管（水猿确认）
**状态**：批准，待 writing-plans 出实现计划

---

## §1 范围与产物

**目标**：3 套独立 Remotion 项目可分别 `npm run dev` 预览，每套 10 个真实 Scene，覆盖封面→收尾完整 SRT。

**不做**：
- voiceover.wav 生成（TTS 跳过；预览静默）
- 渲染 mp4 / 烧字幕
- 封面 HTML（cover-design 后续走）
- publish-kit

**静默预览策略**：
- 所有 Scene 不挂 `<Audio>` 组件
- audioConfig 的 `audioFile` 字段保留（为后续补 wav 不改 Scene）
- Composition 层不引用 audioFile

**公共底料**（三套共用）：
- `production/timing/scene-boundaries.md`（本设计 §2 落地）
- `production/timing/wav-durations.json`（复用现有）

**三套各自**：完整 `remotion-a/`、`remotion-b/`、`remotion-c/` 子目录，含独立 node_modules、独立 `src/scenes/`、独立配色 token。

---

## §2 场景边界（按 SRT 实测时间锚定，三套共用）

| # | id | 进入 | 终 | 时长(s) | 帧(30fps) | 锚点 SRT# | 话题 |
|---|---|---|---|---|---|---|---|
| 1 | s01-cover | 00:00.000 | 00:12.780 | 12.78 | 383 | 1-4 | 封面：AI 时代 Postgres 怎么成默认 |
| 2 | s02-phenomenon | 00:12.780 | 01:22.720 | 69.94 | 2098 | 5-35 | 现象：Agent 推荐 + 生态推动 + 反例小插曲 |
| 3 | s03-corpus-jsonb | 01:22.720 | 02:22.800 | 60.08 | 1802 | 36-63 | SQL 训练语料占比 + DDL 可执行 + JSONB |
| 4 | s04-one-db | 02:22.800 | 03:05.280 | 42.48 | 1274 | 64-79 | OLTP + LangGraph PostgresSaver 同库 |
| 5 | s05-pgvector | 03:05.280 | 03:30.960 | 25.68 | 770 | 80-90 | pgvector 同库起步 |
| 6 | s06-supply | 03:30.960 | 04:20.540 | 49.58 | 1487 | 91-113 | Supabase/Neon/RDS + Prisma/Drizzle + Cookbook |
| 7 | s07-vs-dedicated | 04:20.540 | 05:23.860 | 63.32 | 1900 | 114-142 | pgvector vs 专用库 + Firecrawl 回归 |
| 8 | s08-anti-cases | 05:23.860 | 06:29.480 | 65.62 | 1969 | 143-174 | SQLite/Mongo/两库/serverless + 上云背景收束 |
| 9 | s09-checklist | 06:29.480 | 07:26.880 | 57.40 | 1722 | 175-203 | 五条决策清单 |
| 10 | s10-outro | 07:26.880 | 07:59.200 | 32.32 | 970 | 204-220 | 抄作业生态 + 收尾 |

**合计 = 14375 帧 ÷ 30fps = 479.17s = SRT 末帧 7:59.20 - 33ms ✓（1 帧误差可忽略）**

**两处归属决策（已批）**：
- s02 末段 25-35（反例小插曲）→ 归 s02，作为现象段内"压倒性"收束
- s08 末段 170-174（上云背景）→ 归 s08，作为反例段收束尾

---

## §3 三套视觉路线

### 方案 A · 多隐喻分布式（remotion-a/）

| 维度 | 取值 |
|---|---|
| 色彩 | `accent #4f9ad6`（PG 蓝）+ `accentWarm #f0a868`（生态金）+ `debateFast #6ec87a / debateSlow #a585f0`（对比场） |
| 背景策略 | 每场专属 aura：s01 同心轨道环 / s02 流程河 / s03 代码雨 / s04 立柱光 / s05 网格波纹 / s06 云朵漂浮 / s07 左右半场对比天幕 / s08 边界栅栏 / s09 五条放射光 / s10 海量代码片段堆叠 |
| 主隐喻库（`src/scenes/svg/`） | s01 ConcentricLayers / s02 PromptFlowRiver / s03 CorpusBarChart + JsonbPills / s04 LayeredInstance + DataFlowArrows / s05 ExtensionBadge / s06 SupplyFunnel / s07 SplitVerdict + TimelineMigration / s08 BoundarySpectrum / s09 ChecklistCards / s10 CopyPaperStack |
| 字号尺度 | 标题 140px、副标题 60px、卡标题 52px、正文 44px、SVG text 32-40px |
| 风格关键词 | "证据分布"——每场单独抓眼 |

### 方案 B · 三幕克制叙事（remotion-b/）

| 维度 | 取值 |
|---|---|
| 色彩 | 暖灰极简：`accent #e8a090`（红铜）+ `text #f1efea` + 三幕渐变（白→蓝 / 白→金 / 白→紫） |
| 背景策略 | 三幕同色调：幕 I（s01-s03）冷蓝雾 / 幕 II（s04-s07）金色光斑 / 幕 III（s08-s10）紫罗兰渐隐；同幕内场景背景一致 |
| 主隐喻库 | 5 套通用模板复用：PhenomenonFlow（s02/s06）/ StackedLayers（s03/s04）/ SideBySide（s05/s07）/ SpectrumGrid（s08）/ NumberedCards（s09 + s01/s10 变体） |
| 字号尺度 | 标题 160px、正文 48px |
| 风格关键词 | "幕间留白" |

**反模式风险**：复用模板时按场景内容换填核心数据/标签（StackedLayers 在 s03 是 SQL/JSONB 两层、在 s04 是 OLTP/Checkpoint/Vector 三层），避免视觉同质化。

### 方案 C · Postgres 实例为主角（remotion-c/）

| 维度 | 取值 |
|---|---|
| 色彩 | Postgres 品牌深蓝 `#336791` 为主，accentLit 高亮当前生长的层 |
| 背景策略 | 全片同一片"机房深空"——星点 + 大象 logo 水印 |
| 主隐喻库 | 一个核心组件 `PostgresInstanceCanvas`，受控参数 `phase`（1-10）决定显示哪些层/扩展/外壳/对手 |
| 字号尺度 | 实例占画布 60%+，标题 130px、旁白卡 44px |
| 风格关键词 | "积木生长" |

**反模式风险**：s09 决策清单 + s10 收尾不属生长叙事——`PostgresInstanceCanvas` 缩到右下角，左侧出决策清单/收尾文字。

---

## §4 项目布局

```
features/content-pipeline/postgres-ai-agent-default-db-mid-video/
├── production/
│   ├── content/                          # 已就绪
│   ├── subtitles/sub.srt                 # 已就绪（220 条）
│   ├── timing/
│   │   ├── scene-boundaries.md           # 本设计 §2 落地（三套共用）
│   │   ├── video-input.json              # 已就绪
│   │   └── video-input.example.json
│   └── media/                            # 缺 voiceover.wav（预览阶段不补）
├── remotion-a/                           # 方案 A 独立项目
│   ├── package.json
│   ├── src/
│   │   ├── audioConfig.ts                # 按 §2 表生成（静默策略）
│   │   ├── scenes/
│   │   │   ├── index.tsx                 # SceneRouter
│   │   │   ├── Scene01Cover.tsx ... Scene10Outro.tsx
│   │   │   └── svg/                      # A 专属 10 个 SVG 隐喻组件
│   │   └── shared/                       # cli.mjs init 复制
│   └── public/audio/                     # 占位（暂无 wav）
├── remotion-b/                           # 方案 B 独立项目（结构同上）
└── remotion-c/                           # 方案 C 独立项目（结构同上）
```

---

## §5 实现策略

**串行不现实**：3 × 10 = 30 个真实 Scene，主线一条条写 context 必爆。

**用 SKILL 提供的 workflow**：`skills/remotion-pipelines/workflows/gen-scenes.workflow.mjs` 并行生成场景，每场独立 agent + 自带字号/SVG viewBox/SceneBackground/SRT 对齐 audit。

**分阶段执行**：
1. **阶段 1**（共用底料）：生成 `scene-boundaries.md`
2. **阶段 2**（脚手架 ×3）：分别 `node skills/remotion-pipelines/cli.mjs init <project-dir>` 三次 + 跨平台 compositor 注入 + `npm install`
3. **阶段 3**（配色 token ×3）：按方案 A/B/C 覆盖各项目 `src/shared/colors.ts` `typography.ts`
4. **阶段 4**（audioConfig ×3）：按 §2 表手填，静默策略
5. **阶段 5**（Scene 批量生成）：`gen-scenes.workflow.mjs` 并行 30 个 agent
6. **阶段 6**（预览验证）：每套 `npm run dev` 试跑，跳到关键帧检查无运行时错误

**审计/质量门控**：
- gen-scenes 自带的字号/viewBox/SceneBackground/SRT 对齐 audit 在生成时执行
- 不跑 post-render-audit（无渲染）
- 30 个 Scene 不可能一轮高质量；预览后由水猿挑出需重写的场景，再次走 workflow

---

## §6 验收（预览阶段门控）

- [ ] `production/timing/scene-boundaries.md` 与 §2 表完全一致
- [ ] 三套 `remotion-a/b/c/` 都能 `npm install` 无错
- [ ] 三套都能 `npm run dev` 启动 Remotion Studio
- [ ] 每套 Studio 侧边栏可见 PostgresAIAgent composition，时长 ≈ 7:59
- [ ] 跳到任意场景中间帧（如 50%、80%）：标题/SVG/底栏三区无相互压盖
- [ ] 每套 audioConfig 总帧 = 14375（479.17s × 30，与 SRT 末帧 479.20s 差 33ms = 1 帧）
- [ ] Composition 层不挂 `<Audio>`，预览静默

---

## §7 开放项 / 后续

- voiceover.wav 后续补：水猿手动跑 `volc-podcast-tts action=0`，补到 `production/media/`；再决定要不要在 Composition 加 `<Audio>` 重新预览
- 渲染 + 烧字幕：本次范围外，预览看完水猿挑定主推方案后再开
- 封面 HTML：`skills/cover-design` 后续走
- 三套同时维护成本：shared 修改需手动同步三处，后续可考虑 symlink 或抽公共包

---

## §8 风险

| 风险 | 缓解 |
|---|---|
| 30 Scene 工作量爆炸 | 用 gen-scenes workflow 并行；预览不追求精修，先骨架 |
| 三套独立 node_modules ≈ 1.5GB | 接受；预览后可删未选方案 |
| Scene 一轮生成质量不齐 | 接受；水猿挑选后定向重写 |
| Composition 静默状态下时长校验缺音频锚 | audioConfig 总帧严格按 §2 表，与 SRT 末帧 479.20s 对账 |
| 方案 C `PostgresInstanceCanvas` 在 s09/s10 拖戏 | 设计已约定缩到右下角让位 |
