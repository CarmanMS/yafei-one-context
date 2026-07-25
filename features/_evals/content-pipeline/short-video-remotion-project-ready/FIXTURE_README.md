# 评测 fixture · short-video-remotion-project（remotion-ready 截面）

本目录是 skill 评测的**固定输入快照**。当前进度截面：srt + voiceover 已就绪，待 cc 起一个完整 Remotion 前端工程（脚手架 + audioConfig + 真实 scene 组件）。

## 被以下 scenario 引用

- `skills/remotion-pipelines/evals/short-video-remotion-project/scenario.yaml`

（若新增 scenario 复用本 fixture，请在此处登记。）

## 修改注意事项

- 修改本目录会影响**所有引用此 fixture 的 scenario 的 baseline**，请慎重。
- 修改时 commit message 必须含 `[eval-fixture]` 标签（`meta/lint/eval_fixture_guard.py` 会在 commit-msg hook 里 warn）。
- 修改后建议跑一遍引用此 fixture 的所有 scenario 看 baseline diff。
- **不要**在此目录手动跑 cc 产出文件并 commit（防止污染下次评测输入）；`.gitignore` 已经把 `remotion/` 与 `node_modules/` 列入忽略。

## 命名约定

目录名后缀 `-remotion-project-ready` 表示**进度截面**（srt+wav 就绪、待 cc 起完整 Remotion 工程）。其他截面按需另开目录，不要在同一目录里换截面。

## 与姐妹 fixture 关系

- `short-video-audioconfig-ready/`：只测 `generate-audioconfig.mjs` 一个工具脚本，srt+wav 内容相同。
- 本目录：测 cc 从 srt+wav 出发起整个 Remotion 工程的能力（init + audioConfig + scene + 路由）。
