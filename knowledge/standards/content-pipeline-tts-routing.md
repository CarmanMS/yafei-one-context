# content-pipeline 口播 / TTS 路由（立项默认）

> 来源：one-context 内部约定（2026-05-25，workflows 选题复盘）

## 默认策略（新建 feature 必须遵守）

| 项 | 默认值 | 说明 |
|----|--------|------|
| 模式 | `duo` | `solo`（单人旁白）或 `duo`（双人播客），立项时选定 |
| 引擎 | `volc-podcast-tts`（duo）/ `doubao-dialogue-tts`（solo） | 由 mode 自动路由 |
| **action** | **`0`** | duo 专用；solo 时忽略 |
| 时间轴真源 | **`wav_srt`** | 成片以 `media/voiceover.wav` + `subtitles/sub.srt` 为准 |
| 讲稿角色 | **结构参考**（duo）/ **TTS 直接输入**（solo） | duo: `00-podcast-source.md`；solo: `01-script.md` |

**立项时禁止**在未填 `tts.override_reason` 的情况下把 spec 写成 action=3。

## 三条路径

### 路径 S — 单人旁白（`mode: solo`）

适用：需要精确逐字念稿、单人讲解/教程、画面与口播严格对齐。

| 步骤 | 产出 |
|------|------|
| 写 `01-script.md` | 逐字稿（纯文本，不带 `男：/女：` 前缀） |
| 写 `00-structure.md` | Scene 大纲 |
| TTS | `doubao-dialogue-tts --mono` |
| 后续 | Whisper → `srt-proofread` → `scene-boundaries` / Remotion `audioConfig` |

### 路径 A — 播客总结（`mode: duo`，**默认**）

适用：素材来自 **微信稿 / 文章 / URL / 结构化摘要**；接受服务端改写口播；画面跟 **SRT** 切 Scene。

| 步骤 | 产出 |
|------|------|
| 写 `00-podcast-source.md` | 长文要点 + 钩子 + 固定关注句（给 action=0） |
| 写 `00-structure.md` | Scene 大纲（口播**预期**话题，非逐字稿） |
| 可选 `01-script.md` | 仅结构/核对表，标注「非 TTS 输入」 |
| `timing/video-input.json` | `podcastTts.action: 0`，`scriptPath: content/00-podcast-source.md` |
| TTS | `volc-podcast-tts --action 0` 或流水线 `podcastTts` |
| 后续 | Whisper → `srt-proofread` → `scene-boundaries` / Remotion `audioConfig` |

参考：`features/content-pipeline/ai-companies-build-ai-mid-video/`

### 路径 B — 逐字对白（`mode: duo` + `action: 3`，**例外**）

适用：已有人审定稿、法律/品牌要求 **逐字**、或口播与画面已按句锁死。

| 要求 | 说明 |
|------|------|
| spec `tts.action` | **`3`** |
| spec `tts.override_reason` | **必填**（一句业务理由） |
| TTS 输入 | **仅** `男：`/`女：` 体（无 YAML frontmatter）；或独立 `01-dialogue-volc.md` |
| 禁止 | 把带 frontmatter 的 `01-script.md` 直接喂 CLI |

参考：`features/content-pipeline/markdown-html-claude-engineer-mid-video/`（对白终稿）

## 与成片技术栈无关

| 成片 | 路径 S/A/B 均适用 |
|------|----------------|
| `html-video-from-slides` | `video-input.json` + flip-boundaries |
| `remotion-pipelines` | `scene-boundaries.md` + `audioConfig.ts`；真源仍是 WAV+SRT |

**Remotion 不等于 action=3。** 选 Remotion 仍默认 action=0，除非走路径 B 并声明理由。

## spec 必填 frontmatter（content-pipeline）

```yaml
category: content-pipeline
tts:
  engine: volc-podcast-tts     # duo 时自动；solo 时路由到 doubao-dialogue-tts
  mode: duo                    # solo | duo（默认 duo，缺省等价 duo）
  action: 0                    # duo 专用；solo 时忽略
  authority: wav_srt
  override_reason: ""          # action 非 0 时必填非空（duo 专用）
```

复制完整正文骨架：`features/_template/spec-content-pipeline.md`

## 代理门禁（执行 TTS 前）

1. 读 `spec.md` 的 `tts.mode`（缺省=`duo`）。
2. 若 `mode=duo`：
   a. 读 `tts.action`。
   b. 若为 `0`：确认存在 `00-podcast-source.md` 且 `video-input.json` 中 `podcastTts.action` 为 `0`（或未建 json 则 CLI 显式 `--action 0`）。
   c. 若为 `3`：确认 `tts.override_reason` 非空，且用户曾在 `review_record.md` 确认。
3. 若 `mode=solo`：
   a. 确认存在 `01-script.md` 且非空。
   b. 忽略 `action` / `override_reason` 字段。
   c. 使用 `doubao-dialogue-tts --mono`。
4. **禁止**因「写了双人 `01-script.md`」就自动改 action=3。
5. **禁止** `mode=solo` 时使用 `volc-podcast-tts`。

## 相关文档

- `skills/volc-podcast-tts/SKILL.md`
- `skills/html-video-from-slides/references/VIDEO_PIPELINE.md`
- `features/_template/content-production/README.md`
- `knowledge/standards/video-voiceover-script-conventions.md`（钩子 + 固定句仍须满足）
