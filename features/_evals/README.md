# `features/_evals/` — 共享评测 fixture 池

本目录是 **skill 评测专用的固定输入快照** 共享池（ISS-022 / tech_design §3.1）。

`_*` 前缀让 PM agent 自动跳过本目录（不会出现在 `features/INDEX.md`、不会被 `onecxt feature` 视为正在做的 feature）；与 `features/_template/` 一级目录并列。

## 目录结构

```
features/_evals/
  <category>/
    <feature-id>-<progress-slice>/
      FIXTURE_README.md     # 谁引用了我 + 修改注意事项
      .gitignore            # 屏蔽 cc 评测时应产出的路径，防止污染下次输入
      spec.md
      production/...
```

进度截面后缀（`-content-ready` / `-cover-ready` / `-script-ready`）按 tech_design §3.5 规范填写，表示快照所处的 pipeline 进度。

## scenario.yaml 如何引用

```yaml
target_path: features/_evals/<category>/<feature-id>-<slice>/
```

可选 `overlay.apply:` 单文件 patch 层（不要复制整子树）：

```yaml
overlay:
  apply:
    - src: patches/spec-override.md
      dst: '{{ target_path }}spec.md'
```

`{{ target_path }}` 会被 runner 替换成 scenario 的 `target_path` 字面值。

## 修改这里的内容时

1. 改前先看目录里的 `FIXTURE_README.md`：哪些 scenario 引用了我？
2. Commit message 加 `[eval-fixture]` 标签，便于审计 + baseline diff 触发（commit-msg hook `meta/lint/eval_fixture_guard.py` 会 warn 但不阻断）。
3. 改完跑一遍所有引用此 fixture 的 scenario，看 baseline 是否需要更新。
4. **不要**在此目录手动跑 cc 产出文件并 commit（`.gitignore` 会兜底，但避免误删）。

## 安装 commit-msg hook

```bash
meta/lint/install_hooks.sh
```

幂等；重复执行覆盖最新版本。会保留你已有的 `.git/hooks/commit-msg.local` 作为下游链。
