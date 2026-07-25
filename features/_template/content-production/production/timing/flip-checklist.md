# 成片前翻页确认单（人审）

**用途**：在运行 `node cli.js wav` 之前，用本表做 **≤5 分钟** 定点确认。  
**真源**：`media/*.wav` + `subtitles/sub.srt` + `slides/presentation.html` 可见字；**不用** `00-structure.md` / `01-script.md` 块边界定翻页。

---

## 路径（开工时勾选 — **默认勾选 A**）

- [x] **A. 播客 / action=0（默认）**：口播以 WAV+SRT 为准；TTS 输入为 `00-podcast-source.md`；`01-script.md` 仅参考  
- [ ] **B. 逐字口播 / action=3**：须在 `spec.md` 的 `tts.override_reason` 有理由；`男：`/`女：` 体为 TTS 输入  
- [ ] **C. Edge 分页念稿**：`01-script.md` 的 `# 【】` 块数 = 幻灯页数（非火山双人）

---

## 三条必听时间戳（填秒数后试听 `voiceover.wav`）

| # | 时刻 (s) | 此时口播在讲什么（SRT #） | 画面上应是哪一页 | 通过？ |
|---|----------|---------------------------|----------------|--------|
| 1 | ______ | 封面钩子 / 产品名 | s0 封面 | ☐ |
| 2 | ______ | 第一次专名或数字（如 Trending、星标） | ______ | ☐ |
| 3 | ______ | 第一次大转场（如竞品对比、产品 UI） | ______ | ☐ |

> OpenHuman 示例：① 0s ② ~33–39s 仍 s0（Trending+星标）③ ~39.6s 进 s1（Manus 对比）

---

## `flip-boundaries.md` 一行一问

对表中 **每一行** 问：**「这一秒听到的核心信息，当前页看得见吗？」**

- [ ] 封面页卖点（Trending、星标、钩子）在口播讲完前 **未提前** 切到内页  
- [ ] 过渡句（「接下来」「下面聊」）仍算 **上一页**，未在句首翻页  
- [ ] 最后一页时长闭合到音轨结束（ffprobe 总时长一致）

---

## 代理门禁（全部 ☐ 才可 wav）

- [ ] `timing-check` 无 `FLIP_AT_NEXT_WA_SENTENCE_START` 高危  
- [ ] `slideDurationsSec` 之和 = WAV 时长（误差 ≤1s）  
- [ ] 播客路径：**未**用 `01-script` 块对齐翻页  

---

**确认人**：________　**日期**：________  
**确认后执行**：`skills/html-video-from-slides/scripts/run-wav-build.ps1 -Project "<feature>/production"`
