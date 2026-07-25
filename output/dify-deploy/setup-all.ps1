# ============================================
# Dify 完整搭建脚本 (需以管理员身份运行)
# 使用方法: 右键 → 使用 PowerShell 运行 (管理员)
# ============================================

$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n[步骤] $msg" -ForegroundColor Cyan }
function Write-OK { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[警告] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "[错误] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  Dify 智能体一键搭建脚本" -ForegroundColor Magenta
Write-Host "  教学问答知识库 · 本地部署" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta

# ===== 检查管理员权限 =====
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Err "此脚本需要管理员权限！"
    Write-Host "请右键此文件 → 选择「使用 PowerShell 运行（管理员）」" -ForegroundColor Yellow
    Write-Host "或在 PowerShell (管理员) 中运行: Set-ExecutionPolicy Bypass -Scope Process; & '$PSCommandPath'" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}

# ===== Phase 1: 启用 WSL2 和虚拟化功能 =====
Write-Step "检查 WSL2 和虚拟化功能..."

$needRestart = $false

# 检查 WSL 功能
$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -ErrorAction SilentlyContinue
if ($wslFeature -and $wslFeature.State -ne "Enabled") {
    Write-Host "  启用 WSL 功能..." -ForegroundColor Gray
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart -ErrorAction SilentlyContinue | Out-Null
    $needRestart = $true
    Write-OK "WSL 功能已启用"
} elseif ($wslFeature -and $wslFeature.State -eq "Enabled") {
    Write-OK "WSL 功能已启用"
} else {
    Write-Warn "无法查询 WSL 功能状态，可能被安全策略限制"
    Write-Host "  请手动在「控制面板 → 程序 → 启用或关闭 Windows 功能」中：" -ForegroundColor Yellow
    Write-Host "  1. 勾选「适用于 Linux 的 Windows 子系统」" -ForegroundColor Yellow
    Write-Host "  2. 勾选「虚拟机平台」" -ForegroundColor Yellow
}

# 检查虚拟机平台
$vmFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -ErrorAction SilentlyContinue
if ($vmFeature -and $vmFeature.State -ne "Enabled") {
    Write-Host "  启用虚拟机平台..." -ForegroundColor Gray
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart -ErrorAction SilentlyContinue | Out-Null
    $needRestart = $true
    Write-OK "虚拟机平台已启用"
} elseif ($vmFeature -and $vmFeature.State -eq "Enabled") {
    Write-OK "虚拟机平台已启用"
}

if ($needRestart) {
    Write-Host ""
    Write-Warn "系统功能已修改，需要重启电脑才能生效！"
    Write-Host ""
    Write-Host "请按以下步骤继续：" -ForegroundColor Cyan
    Write-Host "  1. 重启电脑" -ForegroundColor White
    Write-Host "  2. 重启后再次以管理员身份运行此脚本" -ForegroundColor White
    Write-Host "  3. 脚本会自动跳过已完成步骤" -ForegroundColor White
    Write-Host ""
    $restart = Read-Host "是否立即重启？(y/n)"
    if ($restart -eq "y" -or $restart -eq "Y") {
        Restart-Computer -Force
    }
    exit 0
}

# ===== Phase 2: 检查/安装 Docker Desktop =====
Write-Step "检查 Docker Desktop..."

$dockerPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$dockerInstalled = Test-Path $dockerPath

if (-not $dockerInstalled) {
    # 尝试通过 winget 安装
    Write-Host "  Docker Desktop 未安装，尝试通过 winget 安装..." -ForegroundColor Gray

    $installerPath = Join-Path $PSScriptRoot "DockerDesktopInstaller.exe"
    if (Test-Path $installerPath) {
        Write-Host "  找到本地安装包: $installerPath" -ForegroundColor Gray
        Write-Host "  运行安装程序（会弹出 UAC 提示，请点击是）..." -ForegroundColor Gray
        Start-Process -FilePath $installerPath -Wait -ArgumentList "install", "--quiet", "--accept-license"
    } else {
        Write-Host "  未找到本地安装包，使用 winget 安装..." -ForegroundColor Gray
        winget install Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    }

    # 检查安装结果
    $dockerInstalled = Test-Path $dockerPath
    if (-not $dockerInstalled) {
        Write-Warn "Docker Desktop 安装可能未完成"
        Write-Host "  请手动安装: 下载 Docker Desktop Installer.exe 并运行" -ForegroundColor Yellow
        Write-Host "  下载地址: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -ForegroundColor Yellow
        Write-Host "  安装完成后重新运行此脚本" -ForegroundColor Yellow
        Read-Host "按回车退出"
        exit 1
    }
}

Write-OK "Docker Desktop 已安装"

# 检查 Docker Engine 是否运行
Write-Step "检查 Docker Engine 是否运行..."
$dockerRunning = $false
try {
    $dockerInfo = & "C:\Program Files\Docker\Docker\resources\bin\docker.exe" info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerRunning = $true
        Write-OK "Docker Engine 正在运行"
    }
} catch {}

if (-not $dockerRunning) {
    Write-Host "  Docker Engine 未运行，尝试启动 Docker Desktop..." -ForegroundColor Gray
    $dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktopPath) {
        Start-Process -FilePath $dockerDesktopPath
        Write-Host "  等待 Docker Engine 启动（最多等待 120 秒）..." -ForegroundColor Gray

        $waited = 0
        while ($waited -lt 120) {
            Start-Sleep -Seconds 5
            $waited += 5
            try {
                $null = & "C:\Program Files\Docker\Docker\resources\bin\docker.exe" info 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $dockerRunning = $true
                    break
                }
            } catch {}
            Write-Host "  已等待 $waited 秒..." -ForegroundColor DarkGray
        }
    }

    if (-not $dockerRunning) {
        Write-Err "Docker Engine 启动失败"
        Write-Host "  请手动启动 Docker Desktop 并等待右下角图标变绿后，重新运行此脚本" -ForegroundColor Yellow
        Read-Host "按回车退出"
        exit 1
    }
    Write-OK "Docker Engine 已就绪"
}

# ===== Phase 3: 部署 Dify =====
Write-Step "开始部署 Dify 社区版..."

$bashPath = "C:\Program Files\Git\bin\bash.exe"
if (-not (Test-Path $bashPath)) {
    # 尝试其他路径
    $bashPath = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
    if (-not $bashPath) {
        Write-Err "未找到 Git Bash"
        Write-Host "  请安装 Git for Windows: https://git-scm.com/download/win" -ForegroundColor Yellow
        Read-Host "按回车退出"
        exit 1
    }
}

$deployScript = Join-Path $PSScriptRoot "deploy-dify.sh"
if (-not (Test-Path $deployScript)) {
    Write-Err "未找到部署脚本 deploy-dify.sh"
    Write-Host "  请确保 deploy-dify.sh 与此脚本在同一目录" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}

Write-Host "  运行部署脚本..." -ForegroundColor Gray
& $bashPath -c "cd '$PSScriptRoot' && bash deploy-dify.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-OK "Dify 部署完成！"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  下一步操作" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  1. 浏览器访问 http://localhost:3000" -ForegroundColor White
    Write-Host "  2. 注册管理员账号" -ForegroundColor White
    Write-Host "  3. 配置 LLM 模型（设置 → 模型供应商）" -ForegroundColor White
    Write-Host "  4. 创建知识库，上传教学资料" -ForegroundColor White
    Write-Host "  5. 创建 Agent 应用，关联知识库" -ForegroundColor White
    Write-Host ""
    Write-Host "  详细操作指南: 打开 setup-guide.html" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Err "部署脚本执行出错"
    Write-Host "  请查看上方错误信息" -ForegroundColor Yellow
}

Write-Host ""
Read-Host "按回车退出"
