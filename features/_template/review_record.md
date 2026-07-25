# 评审记录 — {{feature-id}}

## 立项门禁（content-pipeline · 执行 TTS 前必过）

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | `spec.md` frontmatter 含 `tts.action` | ☐ |
| 2 | **默认**：`tts.action` = **0**，且存在 `production/content/00-podcast-source.md` | ☐ |
| 3 | `production/timing/video-input.json` 中 `podcastTts.action` 与 spec 一致 | ☐ |
| 4 | 若 `tts.action` ≠ 0：`tts.override_reason` 已填 + **用户本行确认** | ☐ |

**用户确认（action=0 默认可勾「采用默认路径 A」）**：

- [ ] **路径 A（默认）**：action=0，`00-podcast-source.md` 为 TTS 输入，成片以 WAV+SRT 为准  
- [ ] **路径 B（例外）**：action=3，理由：________________________  

确认人：________　日期：________

---

## 变更记录

（按日期追加）
