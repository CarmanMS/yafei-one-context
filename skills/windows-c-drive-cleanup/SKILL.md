---
name: windows-c-drive-cleanup
description: Windows C 盘空间紧张时的安全清理流程。先只读统计；删除、prune、清空回收站必须逐项获得用户明确授权。
---

# Windows C 盘安全清理

## 硬约束

- 默认只做只读统计和预览。不得把“磁盘满了”推定为删除授权。
- 删除、缓存清理、prune、清空回收站必须逐项说明目标与风险，并取得用户对具体开关的明确同意。
- `invoke-c-drive-cleanup.ps1` 默认仅预览；真正执行还必须显式传 `-Execute` 和 `-ChatAuthorizationNote`。脚本参数不能替代对话授权。
- 不全盘批量删除，不碰文档、桌面、下载、项目目录、`node_modules`，除非用户点名精确路径并另行授权。
- 不直接删除 `WinSxS`、Windows Update 数据、WSL 虚拟磁盘、Visual Studio Installer 包缓存或 Program Files 内容；这些仅走系统/官方入口并单独确认。
- 不回显授权原文或凭证。若清理失败，报告“失败或部分完成”，不得声称全部成功。

## 1. 只读调查

先定位仓库，不要硬编码用户名或盘符：

```powershell
$RepoRoot = (git rev-parse --show-toplevel).Trim()
$SkillRoot = Join-Path $RepoRoot 'skills\windows-c-drive-cleanup'
Get-PSDrive -Name C | Select-Object Used, Free
& (Join-Path $SkillRoot 'survey-c-drive-report.ps1')
```

可选检查：

```powershell
# 快速检查常见缓存路径，不递归测体积
& (Join-Path $SkillRoot 'survey-disk-hints.ps1') -Quick

# Program Files 下一级目录统计，较慢
& (Join-Path $SkillRoot 'survey-c-drive-report.ps1') -IncludeProgramFilesBreakdown

# 详细进度
& (Join-Path $SkillRoot 'survey-c-drive-report.ps1') -Verbose
```

报告中的目录体积可能耗时；应用体积来自卸载注册表的 `EstimatedSize`，只作排序线索。卸载仍使用“设置 → 应用 → 已安装的应用”或软件官方卸载器。

## 2. 形成清理提案

向用户分别列出：

1. 可由白名单脚本执行的项目：对应开关、目标、估计收益、风险。
2. 只能手动完成的项目：准确的系统设置或软件入口。

不要一次请求“全部清理”授权。回收站、Docker `-a`、临时目录等高影响项单独确认。

## 3. 先预览，再执行

预览不会修改磁盘，也不需要复制授权原文：

```powershell
$Cleanup = Join-Path $SkillRoot 'invoke-c-drive-cleanup.ps1'
& $Cleanup -NpmCache -PipCache
```

用户确认预览中的具体开关后，才可执行：

```powershell
& $Cleanup `
  -NpmCache -PipCache `
  -Execute `
  -ChatAuthorizationNote '用户明确同意清理 npm 与 pip 缓存'
```

执行前后各记录一次 `Get-PSDrive -Name C`。不得在未确认时添加 `-Execute`，也不得替用户扩充开关。

## 白名单开关

| 开关 | 行为 | 主要风险 |
|---|---|---|
| `-NpmCache` | `npm cache clean --force` | 后续安装需重新下载 |
| `-PipCache` | `pip cache purge` | 后续安装需重新下载 |
| `-YarnCache` | `yarn cache clean` | 后续安装需重新下载 |
| `-PnpmStorePrune` | `pnpm store prune` | 删除未引用包 |
| `-UserTemp` | 清空 `%TEMP%` 内容 | 先关闭可能占用临时文件的程序；脚本拒绝宽泛路径和重解析点 |
| `-LocalAppDataTemp` | 清空 `%LOCALAPPDATA%\Temp` 内容 | 可能与 `%TEMP%` 相同；不要重复承诺收益 |
| `-RecycleBin` | 清空当前用户回收站 | 不可撤销，单独授权 |
| `-DockerSystemPrune` | `docker system prune -f` | 删除停止容器、未用网络、悬空镜像和构建缓存 |
| `-DockerSystemPruneAll` | `docker system prune -a -f` | 更激进，删除所有未使用镜像；与上一项二选一 |
| `-CondaCleanAll` | `conda clean -a -y` | 包和索引缓存需重新下载 |
| `-DotnetNugetLocalsAllClear` | `dotnet nuget locals all --clear` | NuGet 包需重新还原 |

脚本不得加入任意路径参数或“万能删”开关。Visual Studio Installer 包缓存不在自动白名单中。

## 4. 手动或高风险项目

- 首选“设置 → 系统 → 存储 → 临时文件 / 存储感知”。
- 应用卸载走“设置 → 应用”或官方卸载器。
- Visual Studio 走 Visual Studio Installer 的“修改 / 更多”；不要直接删 `C:\ProgramData\Microsoft\VisualStudio\Packages`。
- Windows 组件仅按微软支持的 DISM/存储清理流程；禁止手删 `C:\Windows\WinSxS`。
- WSL、Docker Desktop 虚拟磁盘与 Windows Update 缓存须另立步骤，确认无运行中任务并取得单独授权。
- 浏览器、Steam、Android Studio 等缓存优先在对应应用 UI 内清理。

## 交付

报告调查范围、用户实际授权的开关、每步结果、失败项，以及清理前后 C 盘可用空间。缓存通常可重新下载；回收站内容不保证可恢复。
