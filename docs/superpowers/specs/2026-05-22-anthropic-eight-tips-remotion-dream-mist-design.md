# Anthropic 八条干货 — Remotion 全片渲染（dream-mist 梦幻主题）

## 元数据

| 字段 | 值 |
|------|------|
| 日期 | 2026-05-22 |
| 状态 | approved（用户口头确认 dream-mist + 全片交付） |
| 归属 feature | `features/content-pipeline/anthropic-next-gen-claude-eight-tips-mid-video` |
| 归属 skill | `skills/remotion-deck` |
| 交付物 | `production/videos/final_remotion.mp4`（245s，混音 + 烧字幕） |
| 非目标 | HTML `wav` 成片、1 分钟短版、新建口播/讲稿 |

## 1. 背景与现状

### 1.1 选题

男女对白中视频：**Anthropic 打造下一代 Claude 的 8 个硬核干货**，钩子「AI 会做梦？」。10 页幻灯（封面 + 8 干货 + 致谢）。

### 1.2 已有资产

| 资产 | 路径 | 状态 |
|------|------|------|
| 内容分块 | `production/timing/content-slabs.json` | ✅ 10 页，`theme: blueprint`（待改） |
| 翻页时长 | `production/timing/wav-durations.json` | ✅ 245s，`slideDurationsSec` 10 项 |
| 页分割 | `production/timing/page-splits.json` | ✅ |
| Remotion 数据 | `production/timing/remotion-data.json` | ⚠️ ~202s，与 wav 不一致 |
| 字幕 | `production/subtitles/sub.srt` | ✅ |
| 口播配置 | `production/timing/video-input.json` | ✅ podcastTts + burnSubtitles |
| 专题 SVG | `skills/remotion-deck/src/diagrams/AnthropicDiagrams.tsx` | ✅ 9 图已注册 |
| HTML 幻灯 | `production/slides/presentation.html` | ✅（Remotion 路径不依赖） |

### 1.3 问题

1. **时长漂移**：`remotion-data.json` 的 `totalDurationMs`（~202580）≠ `wav-durations.json`（245000），须 bridge 重跑。
2. **主题不一致**：`content-slabs.json` 为 `blueprint`，`remotion-data.json` 为 `presentation-c`；用户要求 **梦幻主题**，与「做梦」叙事对齐。
3. **缺 flip-boundaries**：无口播↔翻页人审契约（建议补，非 Remotion 硬依赖）。
4. **spec.md 过时**：仍写 `html-video-from-slides` 为主路径。

## 2. 目标

1. 新增 **`dream-mist`** Remotion 主题：深紫夜空 + 流动 Mesh 背景 + 月银/薰衣草强调色。
2. 全片 **245s** Remotion 渲染 → 混音 → 烧字幕 → `videos/final_remotion.mp4`。
3. 10 页内容与现有 `content-slabs.json` / `AnthropicDiagrams` **不改文案语义**，仅换肤与时长对齐。
4. 成片前 **still 抽帧** 验证 Headless Chrome 可读性（封面、干货三「做梦」、干货八）。

## 3. 主题设计：`dream-mist`

### 3.1 视觉意图

- **氛围**：深夜梦境、月华、薄雾、软光晕；避免 blueprint 的工程硬边。
- **与内容呼应**：封面「AI 会做梦？」、干货三「空闲时做梦整理记忆」——月亮 SVG（`anthropic-cover-moon`）为主视觉锚点。
- **可读性**：遵守 `skills/remotion-deck/references/RENDERING_NOTES.md`（禁透明渐变字、禁 backdrop-filter、SVG 标注 ≥28px）。

### 3.2 Token 规格（`src/themes/dream-mist.ts`）

| Token | 值 | 说明 |
|-------|-----|------|
| `bg` | `#0a0618` | 深紫夜空底 |
| `surface` | `#120a24` | 卡片底 |
| `surface2` | `#1a1030` | 次级面 |
| `text1` | `#f5f0ff` | 主文字 |
| `text2` | `#a89bc4` | 辅助文字 |
| `accentA` | `#a78bfa` | 薰衣草（主强调） |
| `accentB` | `#c4b5fd` | 月银 |
| `accentC` | `#67e8f9` | 薄雾青 |
| `sky` | `#818cf8` | 链接/高亮 |

**排版与装饰**（继承 `presentation-c` 的杂志感 + 梦幻光晕）：

- `typography.variant`: `magazine`
- `cardVariant.style`: `glass`（`rgba(255,255,255,0.04)` 边框，不用 backdrop-filter）
- `background.strategy`: `mesh`，`meshPulseIntensity`: `0.12`（略柔于 presentation-c）
- `animation.style`: `cinematic`
- `coverStyle`: `titleColor: gradient`，`titleShadow: glow`，`coverCenterGlow: true`，`bgGlowCount: 4`，`pillStyle: neon`

### 3.3 背景

- **注册**：`BackgroundRegistry` 中 `'dream-mist': MeshGradientProvider`。
- **Blob 色相**（可选增强）：在 `MeshGradientProvider` 增加按 `theme.id === 'dream-mist'` 切换的 blob HSL 预设（紫 270–290、粉 300–320、青 190–200），使流动背景偏梦幻而非 indigo 产品风。
- **性能**：全片 ~7350 帧 @30fps，Mesh 为 `heavy`；接受 ~15–25 分钟渲染（M1 Pro 量级参考 skill 文档）。

### 3.4 注册清单

| 文件 | 改动 |
|------|------|
| `src/themes/dream-mist.ts` | 新建 |
| `src/themes/index.ts` | `dream-mist` 注册 |
| `src/themes/_registry.json` | 关键词：`做梦`、`梦幻`、`dream`、`moon`、`Claude` |
| `src/backgrounds/BackgroundRegistry.ts` | 映射 MeshGradientProvider |
| `production/timing/content-slabs.json` | `"theme": "dream-mist"` |

`AnthropicDiagrams` 已通过 `useTheme()` 取色，**无需改 SVG 路径**，换主题后自动换 accent。

## 4. 渲染流水线

```text
content-slabs.json (theme=dream-mist)
        +
page-splits.json + wav-durations.json (245s)
        │
        ▼
node skills/remotion-deck/cli.cjs bridge --project production/
        │
        ▼
production/timing/remotion-data.json  (totalFrames = 7350 @30fps)
        │
        ├── still ×3（封面 / p3 做梦 / p8 有意识）
        ├── preview（可选，人工扫动画）
        │
        ▼
node skills/remotion-deck/cli.cjs render --project production/ --concurrency 4
        │
        ▼
tmp 或 videos 下无声 MP4
        │
        ▼
finalize_remotion.cjs：混 media/voiceover.wav + 烧 sub.srt
        │
        ▼
production/videos/final_remotion.mp4
```

### 4.1 Bridge 门控

- `slideDurationsSec` 之和 = **245**（±0.5s）。
- `remotion-data.json` 的 `themeId` = **`dream-mist`**。
- `pages.length` = **10**，与 `content-slabs.pages` 一致。
- 每页 `durationFrames` = `round(slideDurationsSec[i] * fps)`。

### 4.2 音频与字幕

- **WAV**：`production/media/voiceover.wav`（须存在；由既有 volc-podcast-tts 产出）。
- **字幕**：`production/subtitles/sub.srt`；烧录参数读 `wav-durations.json` + `video-input.json`（fontSize 42、barHeight 80）。
- **输出路径**：`wav-durations.json` 已指定 `outputFile: videos/final_remotion.mp4`。

### 4.3 flip-boundaries（建议同步写入）

新建 `production/timing/flip-boundaries.md`：10 行，每行 **累计进入秒 + 锚点 SRT# + 页标题**。数据来源：`wav-durations.json` 前缀和 + `sub.srt` 首条锚点。用于成片前人审「口播讲的要点当前页是否可见」。

## 5. 验收标准

| # | 检查项 | 通过条件 |
|---|--------|----------|
| 1 | 时长 | MP4 时长 245s ±1s |
| 2 | 音画 | 口播与翻页无肉眼明显错位（对照 flip-boundaries） |
| 3 | 字幕 | 烧录清晰；专名 Claude / Anthropic / 做梦 / 单向门 / 双向门 正确 |
| 4 | 主题 | 全片 dream-mist：深紫底 + 流动背景 + 月银强调，无 blueprint 硬边残留 |
| 5 | 图表 | 10 页 SVG 无裁切、无透明字消失、关键标注可读 |
| 6 | 文件 | 交付 `production/videos/final_remotion.mp4` |

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Mesh 背景渲染慢 | `--concurrency 4`；必要时降至 2 防 OOM |
| Headless 渐变字消失 | 封面标题用纯色 + textShadow，不用 background-clip text |
| WAV 缺失 | 渲染前检查 `media/voiceover.wav`；无则先跑 podcastTts |
| remotion-data 与 skill 目录 public 副本不同步 | bridge 写入 feature `timing/`；render 使用 project 路径数据 |
| Remotion 商业授权 | 个人/开源可用；商业发布需自备 license |

## 7. 范围外

- 不修改 `01-script.md` / 口播重新合成（除非 WAV 缺失或用户另提）。
- 不跑 `html-video-from-slides wav` 作为交付路径。
- 不在 `remotion-deck` 外复制 render 脚本到 feature 目录（遵循 skill 一处维护）。
- 不新增第 11 页或改 8 条干货枚举。

## 8. 后续（实现计划阶段）

1. 实现 `dream-mist` 主题 + 注册 +（可选）Mesh blob 梦幻色相。
2. 更新 `content-slabs.json` theme 字段。
3. 补 `flip-boundaries.md`。
4. bridge → still 三门禁 → render → finalize。
5. 更新 feature `spec.md` 成片流水线表增加 remotion-deck 行。

---

**用户确认记录**：2026-05-22，用户选择 **A 全片交付** + **方案① dream-mist 梦幻主题**，回复「ok」批准本设计。
