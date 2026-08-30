---
id: "f-ai-paperwork-import"
title: 'F:\ai 科研资料无损整合与恢复记录'
status: done
category: integrations
primary_repo_id: paperwork
owner: ""
updated: "2026-08-30"
---

# 概述

将移动硬盘 `F:\ai` 中的科研资料、历史版本和 Git 恢复信息整合到已登记的 `paperwork` 仓库，不新建 repo。`paperwork` 已属于 `math-research` workspace，因此它是本次整合的唯一实现仓。

结论必须按保存层级理解：

- 以 2026-08-30 快照时点为准，266 个可见文件、原始 `.git`、目录元数据和 NTFS ADS 均已保存在当前 D 盘本地环境，未发现内容缺口。
- 其中 261 个科研文件进入可提交的导入归档；5 个私人工作文件只保存在本机忽略目录和本地 rescue ref 中。
- 当前 `F:\ai` 只剩 261 个科研文件；它们与快照逐路径、逐字节、逐 SHA-256 一致。快照中的 5 个私人工作文件目前已不在 F 盘，但在 D 盘有两个字节级副本。
- 因本机忽略目录和 rescue refs 不随普通 push/clone 迁移，不能把现状表述为“远端已有完整备份”。

# 目标与非目标

## 目标

- 保留源文件内容、目录、时间戳、属性、ADS、Git 历史、stash、未跟踪树及异常 Git 对象的恢复证据。
- 把科研稿件、第三方文献、构建旁产物、私人工作材料和重复件分层存放。
- 不在受版本控制的文件中泄露私人工作文件名、人员编号或原始 Git 私密元数据。
- 留下可核验的 manifest、SHA-256、恢复 refs、验证命令和本次实际提交。
- 保持源移动硬盘上的科研文件可逐字节核验，并如实记录当前源盘与快照差异。

## 非目标

- 不新建第二个科研 repo，不把资料放入 `knowledge/` 或 `proposals/`。
- 不把私人工作材料、原始 `.git` 或 rescue refs 推送到远端。
- 不在本需求中恢复 F 盘缺少的 5 个私人工作文件；写回移动硬盘需要另行明确授权。
- 不承诺取证级磁盘镜像；ACL、owner/audit 信息、未分配空间和已删除扇区不在范围内。
- 不把模型生成内容当作数学证明、作者身份或文献事实。

# 用户与场景

- 科研工作者在 `math-research` 中继续论文写作、查阅第三方文献和恢复历史稿件。
- 更换电脑或误删文件后，可从 manifest、归档版本、本地完整快照或 rescue refs 核验并恢复。
- 提交或推送前，可明确区分允许进入 Git 的科研资料与必须留在本机的私人材料。

# 事实基线与保存层

| 信息层 | 数量与校验事实 | 当前位置（均相对 `paperwork`） | Git 可迁移性 |
|---|---|---|---|
| 科研可见文件 | 261 文件，222,300,499 bytes | `papers/`、`references/`、`archive/imports/2026-08-30-f-ai/` 等分类目录 | 已提交 |
| 私人工作文件 | 5 文件，5,284,554 bytes；两处 SHA-256 多重集一致 | `archive/imports/2026-08-30-f-ai/private-work/` 与 `local-only-source-snapshot/worktree/` | 本机忽略，不会普通 push |
| 导入时完整 worktree | 266 文件，227,585,053 bytes，32 个目录 | `archive/imports/2026-08-30-f-ai/local-only-source-snapshot/worktree/` | 本机忽略 |
| 原始 `.git` | 5,657 文件，800,145,393 bytes，294 个目录 | `archive/imports/2026-08-30-f-ai/local-only-source-snapshot/dot-git/` | 本机忽略 |
| stash 科研清单 | 243 项；104 个独特版本已物化，139 项由现有对象或 rescue ref 保留 | `archive/imports/2026-08-30-f-ai/versions/`、manifest 与 refs | 物化版本已提交；refs 仅本机 |
| NTFS ADS | 8 个 payload，3,188 bytes | 原文件及 tracked manifest 的 SHA-256/base64 | manifest 可迁移 |
| Git 异常恢复信息 | 1,261 个无正常 refs/reflog 可达对象及 9 个临时 object 文件 | raw `.git` 快照 | 仅本机完整快照可保证 |

关键校验标识：

- 源 HEAD：`fd5237b6e66daa3e605d184fa6567bc94c6a062e`
- 源 stash：`60e9126b3c05e972a1d29e2d7d480b83e5ed5290`
- 源 worktree 快照提交：`ec2690134e2339c8bfc82914347338073256810c`
- 导入时 source status SHA-256：`6BE0F9C768544F9F76DB70DD2641D89DA41045C54EE08BFFF0E8AAB29FA66DDB`
- 当前 source status SHA-256：`6B03E1EBF10E64D9A65DB460F7AC8179FE306B170CD15FE680EA166DD45B3051`；差异对应已不在 F 盘的 5 个私人文件。
- tracked import manifest SHA-256：`BDAC915E1F2FDA97DB1E3615054951027F15FF1232E6BE2A3B52F77367D5223E`
- local-only snapshot manifest SHA-256：`10E9A3D88056B716924CB570F500D7A0ADE09E6D4EF954AEE3FAF625B7CFDF47`

# 过程记录

1. **确认归属**：依据 `meta/repos.yaml` 和 `meta/workspaces.yaml`，复用 repo id `paperwork` 与 workspace id `math-research`，不新增 repo。
2. **冻结源状态**：记录源 HEAD、stash、status hash、可见文件计数、字节数、目录、属性和 8 个 ADS。
3. **建立 Git 恢复锚点**：在目标仓建立 10 个 `refs/rescue/f-ai-*`，覆盖 worktree、stash、base、index、untracked 和中间差异；全部 refs 与 manifest 记录一致。
4. **保存原始环境**：复制完整 worktree 和原始 `.git` 到本机忽略的 `local-only-source-snapshot/`，生成逐文件/逐目录 manifest 并校验 SHA-256。
5. **按隐私拆分**：261 个科研文件进入 tracked manifest；5 个私人工作文件复制到两个本机忽略位置，并从可提交 manifest 中移除具体路径。
6. **物化历史版本**：清点 243 个 stash 科研项，将 104 个独特版本放入 `versions/`；6 个删除状态和 4 个修改状态保留在 Git 状态证据中。
7. **专业分类**：本人/合著成果归 `papers/`，第三方论文归 `references/articles/`，文献分析归 `references/analysis/`，构建旁产物与重复件归 `archive/`。作者为空且源自“投稿6”的稿件标为待确认，不冒充第三方文献。
8. **修正活动路径**：移动 42 篇第三方 arXiv 论文及候选分析，更新 6 个辅助脚本；路径变更前的两份报告另存字节级原版，导入 manifest 不被改写。
9. **本地提交**：导入提交为 `723d1b05cd04da5362eb3c5f3cdae334fdca28eb`；分类提交为 `9f19ff24699d4059b2de15dac0651551de70d667`。分支为 `codex/import-f-ai`，相对本机缓存的 `origin/main` 为 0 behind / 4 ahead；未 fetch、未 push、无 PR。
10. **复核当前源盘**：重新计算 5,923 个快照文件和 326 个目录。快照 0 缺失、0 内容不符；当前 F 盘的 261 个科研文件及原始 `.git` 内容均未变化，F 盘仅缺快照中的 5 个私人工作文件及其目录。

现有脚本使用复制操作保存源内容；仅凭当前证据无法确定上述 5 个文件何时、由谁从 F 盘移除，因此不得继续声称“F 盘完全未改动”。

# 验收标准

- [x] tracked manifest 校验通过：261 个可见科研条目、243 个 stash 科研条目、8 个 ADS payload。
- [x] local-only snapshot 的 5,923 个文件与 326 个目录逐项复核，0 缺失、0 字节或 SHA-256 不符。
- [x] 5 个私人工作文件在 `private-work/` 与完整快照中各有一份，文件数、总字节数和 SHA-256 全部一致。
- [x] 10 个 rescue refs 均存在且对象 ID 与 manifest 一致；目标仓 `git fsck --full --strict` 通过。
- [x] `papers/` 与第三方文献目录完成作者边界分类，活动脚本不再引用旧 arXiv 路径。
- [x] F 盘当前差异、隐私边界、非取证级范围和普通 Git 不可迁移项已明确记录。
- [x] `paperwork` 工作树在提交后为 clean；未执行 push、PR、发布或其他远端写入。

# 实现落点（必填）

- **仓库 id**（`meta/repos.yaml`）: `paperwork`
- **分支 / PR**: `codex/import-f-ai`；无 PR，未 push
- **主要路径或模块**:
  - `archive/imports/2026-08-30-f-ai/manifest.json`
  - `archive/imports/2026-08-30-f-ai/verify.ps1`
  - `archive/imports/2026-08-30-f-ai/local-only-source-snapshot/`（本机忽略）
  - `archive/imports/2026-08-30-f-ai/private-work/`（本机忽略）
  - `papers/`
  - `references/`
  - `archive/duplicates/`

# 关联

- **Workspace**（`meta/workspaces.yaml` id，如有）: `math-research`
- **其他需求目录**（跨类别时链接主从）: 无

# 可复现检查

在 `paperwork` 仓库中：

```powershell
pwsh -NoProfile -File archive/imports/2026-08-30-f-ai/verify.ps1
git fsck --full --strict
git status --short --branch
```

期望导入校验输出：

```text
OK: 261 visible entries, 243 stash entries, 8 ADS payloads
```

完整快照的 `manifest.json` 与 `manifest.sha256` 必须先自校验，再按每个 `files[]` 条目的 `area`、`path`、`bytes` 和 `sha256` 逐项重算；ADS 还需比较 `name`、`bytes`、`sha256` 与 base64 payload。不要重跑一次性导入脚本覆盖现有归档。

在 one-context 根仓中：

```powershell
python -m one_context doctor
python -m pytest packages/one-context/tests -q
git diff --check
```

# 风险与隐私

- 两个私人文件副本都位于当前 D 盘，仍共享单盘故障风险；它们不是独立设备备份。
- `private-work/`、`local-only-source-snapshot/` 和 `refs/rescue/f-ai-*` 不会随普通 clone/push 自动出现。
- raw `.git` 含 reflog、不可达对象、临时对象和潜在私人历史，禁止直接提交或公开上传。
- ADS 在非 NTFS 文件系统上可能无法原样承载；tracked manifest 中的 base64 payload 是跨文件系统恢复依据。
- tracked manifest 保留导入时目标路径；后续分类移动由 `verify.ps1` 映射，避免改写历史证据。
- 本规格不记录 5 个私人文件的文件名和人员编号。

# 开放问题

- 是否把 5 个私人工作文件从本地快照复制回 F 盘，以恢复源盘与导入时快照的一致性？该操作需要明确授权。
- 是否为本机忽略的私人文件和 raw `.git` 建立另一块介质上的加密备份？普通 Git 远端不适合承载这些内容。
- 是否在确认远端状态后推送 `codex/import-f-ai`？当前只保留本地提交。
