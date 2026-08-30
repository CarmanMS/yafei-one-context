#Requires -Version 5.1
<#
.SYNOPSIS
  预览或执行白名单内的 C 盘缓存清理。

.DESCRIPTION
  默认仅预览。实际清理必须同时提供 -Execute、用户明确授权的具体清理开关，
  以及 -ChatAuthorizationNote。脚本不会打印授权原文。

.PARAMETER ChatAuthorizationNote
  实际执行时必填：用户在当前对话中的明确同意原文（8–4000 字符）。

.PARAMETER Execute
  真正执行所选清理。省略时只预览，不修改磁盘。

.NOTES
  不卸载应用，也不删除 Visual Studio Installer 包缓存。
#>

[CmdletBinding()]
param(
  [ValidateLength(0, 4000)]
  [string]$ChatAuthorizationNote = '',

  [switch]$Execute,

  [switch]$NpmCache,
  [switch]$PipCache,
  [switch]$YarnCache,
  [switch]$PnpmStorePrune,
  [switch]$UserTemp,
  [switch]$LocalAppDataTemp,
  [switch]$RecycleBin,
  [switch]$DockerSystemPrune,
  [switch]$DockerSystemPruneAll,
  [switch]$CondaCleanAll,
  [switch]$DotnetNugetLocalsAllClear
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$any = $NpmCache -or $PipCache -or $YarnCache -or $PnpmStorePrune -or $UserTemp -or $LocalAppDataTemp -or $RecycleBin -or $DockerSystemPrune -or $DockerSystemPruneAll -or $CondaCleanAll -or $DotnetNugetLocalsAllClear

if (-not $any) {
  throw '至少指定一个清理开关（例如 -NpmCache）；省略 -Execute 即为预览。'
}

if ($Execute -and $ChatAuthorizationNote.Trim().Length -lt 8) {
  throw '实际执行需要 -ChatAuthorizationNote，内容须为用户对所选清理项的明确授权原文（至少 8 字符）。'
}

function Write-CFree {
  try {
    $drive = Get-PSDrive -Name C -ErrorAction Stop
    Write-Host ('  C: 已用 {0:N2} GB  可用 {1:N2} GB' -f ($drive.Used / 1GB), ($drive.Free / 1GB))
  }
  catch {
    Write-Host '  (无法读取 C: 盘)' -ForegroundColor Yellow
  }
}

function Invoke-Step {
  param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][scriptblock]$Action
  )

  Write-Host ''
  Write-Host ">> $Title" -ForegroundColor Cyan
  if (-not $Execute) {
    Write-Host '   [预览] 未执行' -ForegroundColor DarkGray
    return
  }

  try {
    & $Action
    Write-Host '   完成' -ForegroundColor Green
  }
  catch {
    Write-Host ('   失败或仅部分完成: {0}' -f $_.Exception.Message) -ForegroundColor Yellow
  }
}

function Resolve-SafeTempDirectory {
  param([Parameter(Mandatory = $true)][string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { throw '临时目录路径为空。' }

  $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  if (-not $item.PSIsContainer) { throw "目标不是目录: $Path" }
  if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "拒绝清理重解析点目录: $Path"
  }

  $resolved = [IO.Path]::GetFullPath($item.FullName)
  $trimChars = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
  $normalized = $resolved.TrimEnd($trimChars)
  $root = [IO.Path]::GetPathRoot($resolved).TrimEnd($trimChars)
  if ($normalized -ieq $root) { throw "拒绝清理磁盘根目录: $resolved" }
  if ((Split-Path -Leaf $normalized) -ine 'Temp') {
    throw "拒绝清理非 Temp 目录: $resolved"
  }

  foreach ($broadPath in @($env:USERPROFILE, $env:LOCALAPPDATA, $env:SystemRoot)) {
    if ([string]::IsNullOrWhiteSpace($broadPath)) { continue }
    $broad = [IO.Path]::GetFullPath($broadPath).TrimEnd($trimChars)
    if ($normalized -ieq $broad) { throw "拒绝清理宽泛目录: $resolved" }
  }

  return $resolved
}

function Remove-SafeTempContents {
  param([Parameter(Mandatory = $true)][string]$Path)

  $safePath = Resolve-SafeTempDirectory -Path $Path
  foreach ($child in Get-ChildItem -LiteralPath $safePath -Force -ErrorAction Stop) {
    if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      Write-Warning "跳过重解析点: $($child.FullName)"
      continue
    }
    Remove-Item -LiteralPath $child.FullName -Recurse -Force -ErrorAction Stop
  }
}

Write-Host '=== invoke-c-drive-cleanup（白名单清理）===' -ForegroundColor Cyan
Write-Host ('  模式: {0}' -f $(if ($Execute) { '执行' } else { '预览' }))
if ($Execute) {
  Write-Host ('  授权记录: 已提供（{0} 字符，不回显）' -f $ChatAuthorizationNote.Length)
}
Write-Host '  当前 C:' -ForegroundColor DarkGray
Write-CFree

if ($NpmCache) {
  Invoke-Step 'npm cache clean --force' {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'npm 不在 PATH' }
    & npm cache clean --force
    if ($LASTEXITCODE -ne 0) { throw "npm 退出码 $LASTEXITCODE" }
  }
}

if ($PipCache) {
  Invoke-Step 'pip cache purge' {
    if (-not (Get-Command pip -ErrorAction SilentlyContinue)) { throw 'pip 不在 PATH' }
    & pip cache purge
    if ($LASTEXITCODE -ne 0) { throw "pip 退出码 $LASTEXITCODE" }
  }
}

if ($YarnCache) {
  Invoke-Step 'yarn cache clean' {
    if (-not (Get-Command yarn -ErrorAction SilentlyContinue)) { throw 'yarn 不在 PATH' }
    & yarn cache clean
    if ($LASTEXITCODE -ne 0) { throw "yarn 退出码 $LASTEXITCODE" }
  }
}

if ($PnpmStorePrune) {
  Invoke-Step 'pnpm store prune' {
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw 'pnpm 不在 PATH' }
    & pnpm store prune
    if ($LASTEXITCODE -ne 0) { throw "pnpm 退出码 $LASTEXITCODE" }
  }
}

if ($UserTemp) {
  Invoke-Step "清空 %TEMP% 下内容（目标: $env:TEMP；保留目录本身）" {
    Remove-SafeTempContents -Path $env:TEMP
  }
}

if ($LocalAppDataTemp) {
  $localTemp = Join-Path $env:LOCALAPPDATA 'Temp'
  Invoke-Step "清空 LocalAppData\Temp 下内容（目标: $localTemp；保留目录本身）" {
    Remove-SafeTempContents -Path $localTemp
  }
}

if ($RecycleBin) {
  Invoke-Step '清空回收站（当前用户，不可撤销）' {
    if (-not (Get-Command Clear-RecycleBin -ErrorAction SilentlyContinue)) { throw 'Clear-RecycleBin 不可用' }
    Clear-RecycleBin -Force -ErrorAction Stop
  }
}

if ($DockerSystemPruneAll) {
  Invoke-Step 'docker system prune -a -f（激进：删除未使用镜像/容器/网络等）' {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'docker 不在 PATH' }
    & docker system prune -a -f
    if ($LASTEXITCODE -ne 0) { throw "docker 退出码 $LASTEXITCODE" }
  }
}
elseif ($DockerSystemPrune) {
  Invoke-Step 'docker system prune -f（保留非悬空的未使用镜像）' {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'docker 不在 PATH' }
    & docker system prune -f
    if ($LASTEXITCODE -ne 0) { throw "docker 退出码 $LASTEXITCODE" }
  }
}

if ($CondaCleanAll) {
  Invoke-Step 'conda clean -a -y' {
    if (-not (Get-Command conda -ErrorAction SilentlyContinue)) { throw 'conda 不在 PATH' }
    & conda clean -a -y
    if ($LASTEXITCODE -ne 0) { throw "conda 退出码 $LASTEXITCODE" }
  }
}

if ($DotnetNugetLocalsAllClear) {
  Invoke-Step 'dotnet nuget locals all --clear' {
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw 'dotnet 不在 PATH' }
    & dotnet nuget locals all --clear
    if ($LASTEXITCODE -ne 0) { throw "dotnet 退出码 $LASTEXITCODE" }
  }
}

Write-Host ''
Write-Host ($(if ($Execute) { '  清理后 C:' } else { '  当前 C（预览未修改）:' })) -ForegroundColor DarkGray
Write-CFree
Write-Host ''
Write-Host '=== 结束 ===' -ForegroundColor Green
if (-not $Execute) {
  Write-Host '本次仅预览。确认具体开关并取得用户明确授权后，添加 -Execute 与 -ChatAuthorizationNote 才会清理。' -ForegroundColor DarkGray
}
