---
id: "<feature-id>"
title: ""
status: draft
category: content-pipeline
primary_repo_id: one-context
owner: ""
updated: ""
# 口播路由（必填 — 见 knowledge/standards/content-pipeline-tts-routing.md）
tts:
  engine: volc-podcast-tts   # duo 时自动；solo 时路由到 doubao-dialogue-tts
  mode: duo                  # solo（单人旁白）| duo（双人播客，默认）
  action: 0                  # duo 专用，默认 0；仅逐字对白例外用 3；mode=solo 时忽略
  authority: wav_srt         # wav_srt（默认）| script_verbatim（仅 action=3）
  override_reason: ""        # action 不为 0 时必填一句理由，否则立项无效
# 成片栈（二选一或组合）
render:
  stack: remotion-pipelines  # remotion-pipelines | html-video-from-slides
---

# 概述

<!-- 背景、素材来源（URL/本地稿）、目标时长、受众 -->

**口播（立项锁定）**：

| 项 | duo（默认） | solo |
|----|-------------|------|
| TTS | `volc-podcast-tts` action=`0` | `doubao-dialogue-tts --mono` |
| 输入文件 | `production/content/00-podcast-source.md` | `production/content/01-script.md`（逐字稿） |
| 时间轴真源 | WAV + Whisper SRT；`01-script.md` 仅参考 | WAV + Whisper SRT |
| 若 action=3 | 须在 `tts.override_reason` 说明，且 `review_record` 用户确认 | N/A（action 字段忽略） |

# 目标与非目标

## 目标

- [ ] `00-podcast-source.md`（duo/action=0 输入）或 `01-script.md`（solo 输入）+ `00-structure.md`
- [ ] TTS → `media/voiceover.wav`；duo: `video-input.json` 中 `podcastTts.action: 0`；solo: `doubao-dialogue-tts --mono`
- [ ] Whisper `sub.srt` → **`srt-proofread`**
- [ ] `timing/scene-boundaries.md`（话题分组，禁止逐条 SRT 一场景）
- [ ] 成片 + `05-publish-kit.md`
- [ ] `production/cover-prompt.md`（**走 `skills/cover-prompt`**，禁手写堆词）

## 非目标

- 未在 `tts.override_reason` 声明时，**不**使用 action=3 逐字念稿。
- 不把 skill 名、制片 meta 写进观众可见画面。

# 用户与场景

# 验收标准

- [ ] `tts.mode` 与实际使用的 TTS 引擎一致（duo→volc-podcast-tts / solo→doubao-dialogue-tts）。
- [ ] `tts.action` 与 `production/timing/video-input.json` 的 `podcastTts.action` 一致（仅 duo）。
- [ ] 口播含钩子 + 固定关注句（`knowledge/standards/video-voiceover-script-conventions.md`）。
- [ ] Scene/翻页以 **SRT** 对齐，误差 ≤1s。
- [ ] `production/cover-prompt.md` 走 `skills/cover-prompt` 出双版（横 4:3 + 竖 3:4），不手写堆词。

# 实现落点（必填）

- **仓库 id**：one-context
- **内容目录**：`features/content-pipeline/<feature-id>/production/`
- **成片 Skill**：`skills/remotion-pipelines/` 或 `skills/html-video-from-slides/`

# 口播命令速查

## duo 模式（默认 action=0）

```bash
# 推荐：与 VIDEO_PIPELINE 一致
# production/timing/video-input.json → podcastTts.enabled + action: 0

# 或直调 CLI（输入为 00-podcast-source.md，不是 01-script.md）
python skills/volc-podcast-tts/cli.py --action 0 \
  -i features/content-pipeline/<feature-id>/production/content/00-podcast-source.md \
  -o features/content-pipeline/<feature-id>/production/media/voiceover.wav --format pcm
```

## solo 模式

```bash
# 输入为 01-script.md（逐字稿，纯文本，不带 男：/女： 前缀）
python skills/doubao-dialogue-tts/cli.py --mono \
  -i features/content-pipeline/<feature-id>/production/content/01-script.md \
  -o features/content-pipeline/<feature-id>/production/media/voiceover.wav
```

# 关联

# 开放问题
