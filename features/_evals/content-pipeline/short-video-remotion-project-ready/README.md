# short-video-remotion-project-ready

Eval fixture for `skills/remotion-pipelines` — a "short video" feature that
already has SRT + voiceover ready, and is about to bootstrap a full Remotion
front-end project from scratch.

## Layout (输入)

| File | 来源 | 角色 |
|------|------|------|
| `script.srt` | 复用 `short-video-audioconfig-ready/script.srt`（115 段，~5min） | 字幕 + 时长 |
| `voiceover.wav` | 复用 `short-video-audioconfig-ready/voiceover.wav`（5min 静音） | 口播音频 |

## Prompt（评测提示词，cc 应据此产出）

> 我们要把这条短视频做成可用 Remotion 渲染的前端工程，主题是
> **"AI agent 长期记忆"** —— 整体节奏轻量、配色冷暗、信息密度偏低
> （单视频 ~5 分钟，115 字幕段）。
>
> 请用 `skills/remotion-pipelines` 给的能力，在本目录下从零起一个完整的
> Remotion 工程（脚手架 + audioConfig + 至少 1 个真实 scene 组件 +
> 路由 case 注册）。要求工程**结构完整可走 `npm install && npx remotion render`**，
> 不要求实际跑 npm install（评测不联网拉依赖），也不要求出 MP4。

## 期望产出（cc 应交付）

`remotion/`（init 目标子目录）下：

1. `package.json` / `tsconfig.json` / `remotion.config.ts`（来自 init 模板）
2. `src/audioConfig.ts`（由 `generate-audioconfig.mjs` 生成，`SCENES.length === 115`）
3. `src/scenes/index.tsx`（路由器，**至少 1 个 case 不是占位**）
4. `src/scenes/SceneXxx.tsx`（至少 1 个真实场景组件，import `../shared/` 复用 layouts/typography 等）
5. `src/Root.tsx` / `src/index.ts`（来自 init 模板）
6. `public/audio/voiceover.wav`（由 generate-audioconfig 自动 copy）
7. `scripts/generate-audioconfig.mjs` / `scripts/burn-subtitles.mjs`（init 复制）
8. `src/shared/`（init 复制，整目录）

## Why this shape

这个 fixture 测的是 **"从零起一个完整工程"** 的能力（init + 填 audioConfig + 写真实
scene + 注册路由），不是单独测某个工具脚本。比起 `short-video-audioconfig-ready`
（只测 generate-audioconfig.mjs 一个工具），这里 cc 需要：

- 知道有 init 这个口子
- 知道 init 后还要跑 generate-audioconfig
- 知道 scene 不是占位、需要根据 srt 内容写真实组件
- 知道要 import shared/ 复用层

## Provenance

- `script.srt` / `voiceover.wav` 与 `short-video-audioconfig-ready/` 完全相同（共享内容）
- 仅 `README.md` 不同（角色：从"评测脚本"升级到"评测整工程"）
