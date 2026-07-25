# AI 造 AI — remotion-pipelines Cosmic Cycle 双写 + A/B 成片

## 元数据

| 字段 | 值 |
|------|-----|
| 日期 | 2026-05-24 |
| 状态 | approved（用户 2026-05-24 确认「ok」） |
| 归属 feature | `features/content-pipeline/ai-companies-build-ai-mid-video` |
| 归属 skill | `skills/remotion-pipelines` |
|  superseded | `docs/superpowers/specs/2026-05-23-ai-companies-cosmic-cycle-design.md`（remotion-deck 方案，**不再实施**） |
| 非目标 | remotion-deck 扩展；html-video-from-slides 主成片；改口播 WAV；全仓默认 cosmic 背景 |

---

## 1. 目标

1. **双写交付**：`production/slides/presentation.html`（浏览器预览）+ `production/slides/slide-manifest.json`（Remotion 渲染源），内容一致。
2. **Cosmic Cycle 背景**：Nano Banana 式星空 + 昼夜渐变，**composition 级连续相位**；全片约 **390.6s** 内 **2.5 圈** 昼夜循环；**翻页不重置**背景。
3. **Region 布局**：沿用 remotion-pipelines v8 字号与 Region 原子（hero / split / grid / …），主题 **cosmic-cycle**（紫靛青 accent + 玻璃卡白昼可读）。
4. **内容源**：自 `production/timing/content-slabs.json`（10 页）转换 manifest，再对照 SRT 微调 `.wa` / 关键词。
5. **成片 A/B 一次性对比**（用户选定长期方案前两条都产出）：
   - **A — FFmpeg 后处理**：Remotion 静音 MP4 → mux `voiceover.wav` + ASS/SRT 烧录 → `videos/final_remotion_ffmpeg.mp4`
   - **B — Remotion 原生**：`<Audio>` + 字幕组件 → `videos/final_remotion_native.mp4`

---

## 2. 架构

```
content-slabs.json ──► scripts/slabs-to-manifest.cjs ──► slide-manifest.json
        │                        │
        └──── dual-write ────────┴──► presentation.html
                                              │
                    shared cosmic-phase.js ◄──┘ (HTML preview + Remotion 同源相位公式)

wav-durations.json ──► manifest.meta.durationFrames + Sequence 起止帧

Remotion SlideDeck (composition.tsx)
  ├─ CosmicCycleBackground (global, useCurrentFrame)
  │     phase = (frame / totalFrames) * cycleCount   // cycleCount = 2.5
  └─ Sequence × 10 × SlideContent (regions only, 无 per-slide 径向底)

CLI (--project <production>)
  render --audio-mode both
    → tmp/remotion_silent.mp4
    → finalize-ffmpeg.cjs  → videos/final_remotion_ffmpeg.mp4
    → render-native path   → videos/final_remotion_native.mp4
```

### 与 remotion-deck 的切割

| 项 | remotion-deck（废弃本选题） | remotion-pipelines（本方案） |
|----|---------------------------|------------------------------|
| 布局 | 6 固定模板 | Region 自由堆叠 |
| 预览 | Studio / 无 HTML | **presentation.html** |
| 输入 | remotion-data.json | **slide-manifest.json** |
| 背景 | BackgroundProvider 插件槽 | **CosmicCycleBackground** 内建 |
| 本 feature | `timing/remotion-data.json` 仅历史产物 | **不扩展**；新真源为 manifest |

---

## 3. Cosmic Cycle 背景（Canvas2D + 相位渐变）

**选型**：方案 1 — Canvas2D 星场 + CSS/Canvas 渐变插值（**非 WebGL**）。Remotion 每帧 `drawImage` 或重绘星点；HTML 预览共用 `cosmic-phase.ts` 导出的 `getCosmicPalette(phase)` 与星种子。

### 相位

```
totalFrames = round(totalDurationSec * fps)   // 390.6s @ 30fps ≈ 11718
cycleCount = 2.5
phase = (currentFrame / totalFrames) * cycleCount
phaseInCycle = phase % 1
```

### 单圈内分段（与 2026-05-23 一致，重复 2.5 次）

| phaseInCycle | 阶段 | 视觉 |
|--------------|------|------|
| 0.00–0.25 | 深空夜 | 星点最亮、底色 `#0a0a12` 系 |
| 0.25–0.35 | 黎明 | 地平线暖紫 → 靛蓝过渡 |
| 0.35–0.55 | 白昼 | 星点 alpha 降低、天顶 `#4a6fa5` 系、**玻璃卡片**保证正文对比 |
| 0.55–0.65 | 黄昏 | 橙紫回退 |
| 0.65–1.00 | 深夜 | 回到深空 |

### 文件落点

| 路径 | 职责 |
|------|------|
| `skills/remotion-pipelines/src/backgrounds/CosmicCycleBackground.tsx` | Remotion 组件，`useCurrentFrame()` |
| `skills/remotion-pipelines/src/backgrounds/cosmic-phase.ts` | 纯函数：palette、星点伪随机、phase 计算 |
| `skills/remotion-pipelines/public/cosmic-bg.js` 或内联于 HTML | 预览用同一 phase API |

参考灵感：`production/timing/custom-theme.json`（preset B, 2.5 圈）。

---

## 4. slide-manifest 与 Sequence 时序

### 输入

- `production/timing/content-slabs.json` — 10 页 slab（layout / items / svgHint / wa）
- `production/timing/wav-durations.json` — `slideDurationsSec` 数组

### manifest 结构（扩展 meta）

```json
{
  "meta": {
    "title": "AI 公司用 AI 造 AI",
    "totalSlides": 10,
    "fps": 30,
    "totalDurationSec": 390.6,
    "durationInFrames": 11718,
    "background": { "type": "cosmic-cycle", "cycleCount": 2.5 }
  },
  "theme": { "id": "cosmic-cycle", "accent": "#7c6cf0", "bg": "#0a0a12", ... },
  "slides": [ { "id": "s0", "durationSec": 20.1, "regions": [...] }, ... ]
}
```

### composition.tsx 改动要点

1. `loadManifest(manifestPath)` 在 `SlideDeck` 内同步/异步加载（替换 `window.__MANIFEST__` 占位）。
2. 根节点：`AbsoluteFill` → `CosmicCycleBackground` + 子 `Sequence` 列表。
3. 每页：`from = sum(prev durations) * fps`，`durationInFrames = round(durationSec * fps)`。
4. `Slide` 去掉 per-slide 径向渐变底，仅保留 regions + 页码。
5. `RemotionRoot` 的 `durationInFrames` 从 manifest 或 props 注入。

---

## 5. slabs → manifest 转换规则

脚本：`skills/remotion-pipelines/scripts/slabs-to-manifest.cjs`（或 feature `production/scripts/` 薄封装）。

| slab.layout | Region 映射 |
|-------------|-------------|
| Cover | `hero` + `chips` + 可选 `pipeline` |
| SlimHeader + items | `split` 或 `grid`（≤4 卡） |
| Split | `split` |
| Grid2x2 | `grid` |
| Takeaways | `summary` |
| Thanks | `hero`（简化） |

- 保留 slab 内 `wa`、数字、专名到 region blocks。
- `svgHint` → manifest 内 `graphic` 字段或 inline SVG 占位（与 HTML 双写一致）。
- 输出后运行 `node cli.js validate`。

### presentation.html

- 结构参考：`anthropic-founders-playbook-mid-video/production/slides/presentation.html`。
- 每页 DOM 与 manifest 同序；`#P` + `go(n)` 满足 html-video-from-slides 契约（备用）。
- `<script>` 引入 cosmic phase + 星场 canvas，**不**随 `go(n)` 重置 phase（预览用 wall-clock 或 slider 模拟 phase）。

---

## 6. CLI 与成片路径

### 新/扩展命令

```bash
node skills/remotion-pipelines/cli.js render \
  --project features/content-pipeline/ai-companies-build-ai-mid-video/production \
  --audio-mode both
```

| 模式 | 行为 |
|------|------|
| `silent` | 仅 Remotion → `production/tmp/remotion_silent.mp4` |
| `ffmpeg` | silent + `scripts/finalize-ffmpeg.cjs`（mux wav + burn sub.srt） |
| `native` | Remotion `<Audio>` + caption layer |
| `both` | 一次 silent，再 ffmpeg + native 两条成片 |

### 输出

| 文件 | 说明 |
|------|------|
| `production/videos/final_remotion_ffmpeg.mp4` | 路径 A |
| `production/videos/final_remotion_native.mp4` | 路径 B |
| `production/tmp/remotion_silent.mp4` | 中间产物 |

字幕样式对齐 `wav-durations.json` 的 `subtitle` 块（fontSize 42、barHeight 80）。

---

## 7. 质量门控

1. `node cli.js validate` — manifest schema。
2. `node skills/html-video-from-slides/cli.js timing-check --project production` — 翻页与 SRT（若保留 `.wa`）。
3. `/slide-subtitle-sync-review` — 10 页字幕覆盖（Blocking 清零后再交付）。
4. 目视：Remotion 中间帧（`startFrame + 150`）亮度 ≥ 50（见 RENDERING_NOTES 惯例）。
5. A/B 对比记录写入 `production/render-ab-notes.md`（可选，一行结论即可）。

---

## 8. feature 目录变更清单

| 路径 | 动作 |
|------|------|
| `production/slides/presentation.html` | **新建** |
| `production/slides/slide-manifest.json` | **新建**（由 slabs 生成） |
| `production/timing/content-slabs.json` | 可选 `"theme": "cosmic-cycle"` 标注 |
| `production/timing/remotion-data.json` | **不修改**；README 或 spec 标注 deprecated |
| `spec.md` | 更新验收：remotion-pipelines 双写 + cosmic + A/B MP4 |

---

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Canvas 星场 Remotion 渲染慢 | 星点数量上限 ~800；静态 seed；必要时 `@remotion/media-utils` 缓存 |
| 白昼正文对比不足 | cosmic-cycle 主题强制 glass 卡 + 文字 shadow |
| slabs 与 Region 语义损失 | 生成后人工对照 SRT 改 manifest + HTML 同步 |
| FFmpeg vs native 字幕不同步 | timing-check + 同一 `wav-durations.json` 帧轴 |

---

## 10. 自检（Spec Self-Review）

| 检查项 | 结果 |
|--------|------|
| 用户已批准 remotion-pipelines（非 deck） | ✅ |
| 2.5 圈 / 390.6s / 翻页不重置 | ✅ |
| Canvas2D 方案 | ✅ |
| 双写 HTML + JSON | ✅ |
| A/B 音频路径 | ✅ |
| content-slabs 10 页为源 | ✅ |
| 旧 remotion-data 不扩展 | ✅ |
| CLI `--project` 与产出路径明确 | ✅ |

---

## 11. 下一步

1. 用户审阅本 spec（当前步骤）。
2. 按 **writing-plans** skill 生成 `docs/superpowers/plans/2026-05-24-ai-companies-remotion-pipelines-cosmic-plan.md`。
3. 实现 → 渲染 A/B → sync review → 更新 `spec.md`。
