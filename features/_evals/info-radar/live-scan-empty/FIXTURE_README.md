# live-scan-empty

Eval fixture for `skills/info-radar` — 一个**空白容器**，仅用于承接 cc 在评测中落盘的中间产出（`production/info-radar/01..04`）。

## Layout

| Path | Purpose |
|------|---------|
| `production/info-radar/.gitkeep` | 占位空目录，cc 评测时往这里写四个 artifact |
| `.gitignore` | 屏蔽评测产物，防止污染下次输入 |

## Why empty

info-radar 实时扫公网，**真实输入是公网而不是 fixture**。fixture 在这里只起两个作用：

1. 给 scenario 一个稳定的 `target_path:`（runner 要求 scenario 必须声明）
2. 提供 `production/info-radar/` 这个目录路径，让 `eval.yaml` 的 artifacts glob 有地方匹配文件

精简版的 `sources.yaml` 通过 scenario `overlay.apply:` 写入 sandbox 内的 `skills/info-radar/references/sources.yaml`（覆盖 skill 原配置），不在本目录管理。

## Referenced by

- `skills/info-radar/evals/live-scan/scenario.yaml`
- `skills/info-radar/evals/one-liner/scenario.yaml`
