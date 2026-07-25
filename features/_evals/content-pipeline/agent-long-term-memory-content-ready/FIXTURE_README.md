# 评测 fixture · agent-long-term-memory（content-ready 截面）

本目录是 skill 评测的**固定输入快照**。当前进度截面：spec + content 已就绪，待 cc 生成 `production/cover-prompt.md`。

## 被以下 scenario 引用

- `skills/cover-prompt/evals/mid-video/scenario.yaml`

（若新增 scenario 复用本 fixture，请在此处登记。）

## 修改注意事项

- 修改本目录会影响**所有引用此 fixture 的 scenario 的 baseline**，请慎重。
- 修改时 commit message 必须含 `[eval-fixture]` 标签（`meta/lint/eval_fixture_guard.py` 会在 commit-msg hook 里 warn）。
- 修改后建议跑一遍引用此 fixture 的所有 scenario 看 baseline diff。
- **不要**在此目录手动跑 cc 产出文件并 commit（防止污染下次评测输入）；`.gitignore` 已经把 `production/cover-prompt.md` 与 `production/cover/` 列入忽略。

## 命名约定

目录名后缀 `-content-ready` 表示**进度截面**（spec 与 content 素材就绪、待 cover-prompt 阶段产出）。其他截面按需另开目录（例如 `-cover-ready` / `-script-ready`），不要在同一目录里换截面。
