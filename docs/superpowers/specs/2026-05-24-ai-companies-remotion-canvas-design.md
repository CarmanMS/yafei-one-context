# Design Spec: ai-companies-build-ai-mid-video with remotion-canvas

## Overview

使用 `skills/remotion-canvas`（Remotion beat-level video engine）为 content-pipeline 特征 `ai-companies-build-ai-mid-video` 生成逐句精细同步（beat-level）的 MP4 视频。

## Key Decisions

| 决策 | 选择 |
|------|------|
| 音视频同步粒度 | **逐句精细同步 (Beat-level)**：每句字幕独立出入场动画 |
| 视觉风格 | **科技暗色 (Tech Dark)**：深蓝/暗灰画布 + 青色强调色，geometric 背景 |
| 编排方式 | **全自动生成**：`node cli.js full --project <dir>` 一键出片 |
| 实施策略 | **方案 A**：扩展 CLI 文件发现 + 新增品牌配置 |

## Data Flow

```
features/content-pipeline/ai-companies-build-ai-mid-video/production/
  ├─ content/00-structure.md   →  match-style (future), now manual brand
  ├─ subtitles/sub.srt       →  beat-assign
  ├─ content/01-script.md    →  manual section/chunk structure (fallback)
  └─ timing/video-input.json →  audio metadata

skills/remotion-canvas/
  ├─ cli.js findFile          →  增认 production/ 下路径
  ├─ brand-profiles.ts        →  新增 "tech" brand (dark, cyan accent, geometric)
  ├─ pipeline/beat-assign.ts  →  解析 SRT → 段落结构 → beats
  ├─ pipeline/choreograph.ts  →  beats + style + background → beat-manifest.json
  ├─ pipeline/render.ts       →  manifest → Remotion → MP4
  └─ out/final.mp4           ←  生成无音频的 MP4（后续合成）
```

## Approach A: Changes Required

### 1. CLI `findFile` Discovery Paths

`cli.js` 中的 `findFile()` 需增加对 content-pipeline `production/` 目录约定的识别：

```js
// match-style
findFile(args.project, [
  "visual-narrative-out/content-structure.md",
  "content-structure.md",
  "production/content/00-structure.md",        // NEW
]);

// beat-assign SRT
findFile(args.project, [
  "visual-narrative-out/script.srt",
  "script.srt",
  "timing/script.srt",
  "production/subtitles/sub.srt",              // NEW
]);

// beat-assign structure
findFile(args.project, [
  "visual-narrative-out/content-structure.md",
  "content-structure.md",
  "production/content/00-structure.md",        // NEW
]);

// render audio
findFile(args.project, [
  "timing/voiceover.wav",
  "visual-narrative-out/voiceover.wav",
  "voiceover.wav",
  "production/media/voiceover.wav",            // NEW
]);
```

### 2. New Brand: `tech` (Dark Mode)

`cli.js` 的 `generateDefaultStyle()` 和 `brand-profiles.ts` 新增：

| Token | Value |
|-------|-------|
| brand | `tech` |
| canvas | `#0a0e1a` |
| surface1 | `#111827` |
| surface2 | `#1a2234` |
| ink | `#e5e7eb` |
| inkMuted | `#9ca3af` |
| primary | `#0ea5e9` (cyan-500) |
| primarySoft | `#0ea5e918` |
| recommendedBackgrounds | `["geometric", "grid", "nebula"]` |

### 3. CLI Command for This Feature

```bash
cd skills/remotion-canvas
node cli.js full \
  --project ../../features/content-pipeline/ai-companies-build-ai-mid-video \
  --style tech --dark --background geometric
```

### 4. Fallback for Missing Audio

当前无 `voiceover.wav`。Render 阶段将：
1. 检测音频文件缺失
2. 以 `silent` 模式渲染 MP4
3. 输出到 `features/.../videos/final.mp4`
4. 后续可叠加火山播客 WAV（ffmpeg 合成）

## Scope

**In scope:**
- CLI 路径扩展（`findFile`）
- 新增 `tech` brand + dark mode 配色
- 确保 `full` 命令能从 `production/` 目录跑通
- 无音频 MP4 输出

**Out of scope:**
- 火山播客 TTS 集成（已有独立 pipeline）
- ffmpeg 音频混流（后续步骤）
- 从 `01-script.md` 自动生成 section/chunk 结构（需额外 NLP 解析）
- 双人播客 `男：` / `女：` 对白差异化动画

## Risks

| 风险 | 缓解 |
|------|------|
| SRT 约 200+ 条，beat-assign 生成过多 beats | `beat-mapper.ts` 已处理短 beats 合并 (<1.5s) |
| 无 `content-structure.md`，match-style 回退到 default | CLI 已内置 fallback，直接生成 tech brand 风格 |
| choreograph.ts/dual-write.ts 可能依赖未检查的 pipeline 模块 | 需验证 `build` 阶段所有子模块存在且运行正常 |
| 成片中文字体渲染问题 | 确保 `typography` 配置含 `Noto Sans SC` |

## Success Criteria

- [ ] `node cli.js full --project <feature-dir>` 成功跑完四个阶段无 error
- [ ] 输出 `beat-manifest.json` Zod 校验通过
- [ ] 渲染出 `final.mp4`（无音频，画面逐句动画）
- [ ] 视频色调为科技暗色风格，背景为几何线条
