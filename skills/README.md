# skills — 仓库内可复用技能（工具无关）

本目录存放 **跨 Cursor / Claude Code / OpenClaw 等** 共用的自动化流程，与 `knowledge/` 中「给人/模型读的规范」互补：此处偏重 **可执行脚本 + 单一入口**。

| 路径 | 说明 |
|------|------|
| [`cover-design/`](cover-design/) | **封面设计规范**；CONFIG 驱动 HTML 截图封面，4 种预设主题；横竖版模板；被 `html-video-from-slides` 引用 |
| [`html-lottie-cover/`](html-lottie-cover/) | **封面 Lottie 主视觉**；`cover.html` 的 `#hero-deco` 用 lottie-web + JSON（`decoLottie`），失败回退 `decoSVG`；与 `cover` CLI 的 `__coverLottieReady` 门控配合 |
| [`cover-prompt/`](cover-prompt/) | **AI 生图封面提示词**；根据视频主题+品牌色系输出 GPT Image / Flux 提示词（竖版 3:4 + 横版 4:3）；与 cover-design 互补（可两次生成法：AI 出背景 + HTML 叠文字） |
| [`html-video-from-slides/`](html-video-from-slides/) | HTML 幻灯 + 口播 → MP4；**wav-auto** 仅需单个 WAV + HTML（Whisper 自动对齐）；见 `SKILL.md` · 目录分层见同目录 `README.md` |
| [`remotion-pipelines/`](remotion-pipelines/) | **Region 双写 Remotion 成片**；`presentation.html` + `slide-manifest.json` → 浏览器预览 + 帧级 MP4；见 `SKILL.md` |
| [`html-deck-layout/`](html-deck-layout/) | **Mobile PPT 生成器**（1920×1080）：prompt → 手机横屏幻灯片，6 主题 + 7 布局 + 4 全 deck 模板，自动 fill-deck、≥42px 字号、≥85% 覆盖率；可与 `html-video-from-slides` 联动成片；见 `SKILL.md` |
| [`srt-to-deck/`](srt-to-deck/) | **SRT 字幕 → 幻灯片 + 精准翻页时长**；Whisper 转写的 SRT → presentation.html + wav-durations.json；按话题拆页时锁定每页对应的 SRT 条目范围，从时间戳直接算出翻页时长；配合 html-video-from-slides wav 模式无需 Whisper 二次对齐；触发词：SRT转PPT/字幕转幻灯/口播转PPT/srt to presentation；见 `SKILL.md` |
| [`html-slides/`](html-slides/) | HTML 演示幻灯生成（从零/PPT转换，12种样式预设）；多语言 README；见 `SKILL.md` |
| [`fireworks-tech-graph/`](fireworks-tech-graph/) | **技术图表生成**；SVG 架构图/流程图/时序图/UML/ER/网络拓扑等 15+ 图表类型，7 种视觉风格，rsvg-convert 导出 PNG；触发词：画图/架构图/流程图/可视化；见 `SKILL.md` |
| [`skill-parallel-verify/`](skill-parallel-verify/) | **Skill 交付前并行验证**；5 个测试专家独立执行→测试主管判定语义等价→不一致自动修复循环；见 `SKILL.md` |
| [`windows-c-drive-cleanup/`](windows-c-drive-cleanup/) | Windows C 盘清理；**授权后** `invoke-c-drive-cleanup.ps1` 白名单自动清理；只读 `survey-c-drive-report.ps1`（五-A 自动 / 五-B 手动）；见 `SKILL.md` |
| [`project-audit/`](project-audit/) | **项目整理**；审计全量已追踪文件，识别错位/误提交文件，列出清单供确认后执行挪正/排除/清理；触发词：项目整理/审计/清理仓库；见 `SKILL.md` |
| [`doubao-dialogue-tts/`](doubao-dialogue-tts/) | **豆包/火山 TTS**：对口播对白脚本（男：/女：）逐句合成 **WAV**；V3 合成接口纯念稿、不走 AI 播客自动生成；见 `SKILL.md` |
| [`volc-podcast-tts/`](volc-podcast-tts/) | **火山播客 WebSocket v3**：长文本/URL/`nlp_texts` 双人播客流式音频（PCM/WAV/MP3）；与「逐句念稿」TTS 不同；见 `SKILL.md` |
| [`gitsync/`](gitsync/) | **安全 Git 同步**：fetch → 分叉诊断 → ff-only/merge/rebase → 冲突处理；备份分支 + stash，避免本地丢失；触发 `/gitsync`、`git sync`；见 `SKILL.md` |
| [`script-deck-audit/`](script-deck-audit/) | **口播稿 ↔ 幻灯一致性**：讲稿关键术语须在对应 slide 出现；输出句↔页映射；触发「讲稿幻灯一致性」「script deck audit」；见 `SKILL.md` |
| [`ppt-style-loop-correct/`](ppt-style-loop-correct/) | **PPT 样式循环矫正**：逐页截图评估空白/无图/重叠，改 HTML 后重截（每页≤10 轮）；`capture` / `audit-dom` / `run`；见 `SKILL.md` |
| [`html-anything-deck/`](html-anything-deck/) | **产品发布会幻灯片生成**：基于 html-anything deck-product-launch 模板，将产品信息转换为产品发布会 PPT；支持多级定价、特性展示、CTA；触发词：/html-anything-deck、生成发布会PPT；见 `SKILL.md` |
| [`arch-html/`](arch-html/) | **文本 → 交互式架构图 HTML**：从文本/Markdown 描述生成 GoJS 架构图，支持迭代精修（截图比对 / 代码审查一致性）；触发词：arch-html、文本转架构图、架构图HTML生成；见 `SKILL.md` |
| [`review/`](review/) | **方案评审智能体**：多智能体协作交叉评审技术方案，支持双 Agent 对弈 / 多角色委员会两种模式；触发词：方案评审、review、技术方案评审；见 `SKILL.md` |
| [`pmdcheck/`](pmdcheck/) | **PMD Java 静态检查**：自动定位 Maven 项目、执行 PMD 规则集（默认查无效/重复/同包 import），`--fix` 调 AI 智能修复；触发词：PMD检查、静态代码分析、无效import检测；见 `SKILL.md` |
| [`consolecast/`](consolecast/) | **控制台会话录制与讲解**：将控制台输出录制为 `.consolecast` 演示文件，纯 HTML/JS 播放器回放（打字动画 + 流式输出 + 讲解气泡）；触发词：consolecast、录制演示、回放、演示文件；见 `SKILL.md` |

各视频选题目录**不应**再复制一套 Node 脚本；应通过 `--project` 指向仅含素材的文件夹。
