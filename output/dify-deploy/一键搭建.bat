@echo off
chcp 65001 >nul 2>&1
title Dify 智能体一键搭建

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [需要管理员权限] 正在自动提权...
    echo.
    powershell -Command "Start-Process cmd -ArgumentList '/c %~dpnx0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================
echo   Dify 智能体一键搭建脚本
echo   教学问答知识库 - 本地部署
echo ========================================
echo.

:: ===== Phase 1: 启用 WSL2 =====
echo [步骤 1] 检查并启用 WSL2 和虚拟化功能...
echo.

dism /online /get-featureinfo /featurename:Microsoft-Windows-Subsystem-Linux >nul 2>&1
if %errorLevel% equ 0 (
    dism /online /get-featureinfo /featurename:Microsoft-Windows-Subsystem-Linux 2>nul | find "State : Enabled" >nul
    if errorLevel 1 (
        echo   启用 WSL 功能...
        dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
        set NEED_RESTART=1
    ) else (
        echo   [OK] WSL 功能已启用
    )
) else (
    echo   [跳过] 无法通过 DISM 查询，请手动在 Windows 功能中启用
)

dism /online /get-featureinfo /featurename:VirtualMachinePlatform >nul 2>&1
if %errorLevel% equ 0 (
    dism /online /get-featureinfo /featurename:VirtualMachinePlatform 2>nul | find "State : Enabled" >nul
    if errorLevel 1 (
        echo   启用虚拟机平台...
        dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
        set NEED_RESTART=1
    ) else (
        echo   [OK] 虚拟机平台已启用
    )
) else (
    echo   [跳过] 无法通过 DISM 查询虚拟机平台
)

if defined NEED_RESTART (
    echo.
    echo ========================================
    echo   [重要] 系统功能已修改，需要重启电脑！
    echo.
    echo   重启后请再次双击运行此脚本
    echo   脚本会自动跳过已完成步骤
    echo ========================================
    echo.
    set /p RESTART=是否立即重启？(y/n):
    if /i "%RESTART%"=="y" shutdown /r /t 5 /c "Dify setup: restarting to enable WSL2"
    exit /b
)

echo.

:: ===== Phase 2: 安装 Docker Desktop =====
echo [步骤 2] 检查 Docker Desktop...
if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    echo   [OK] Docker Desktop 已安装
) else (
    echo   Docker Desktop 未安装，开始安装...
    echo.
    if exist "%~dp0DockerDesktopInstaller.exe" (
        echo   使用本地安装包: %~dp0DockerDesktopInstaller.exe
        echo   安装中，请耐心等待（约2-3分钟）...
        echo   如果弹出 UAC 提示，请点击"是"
        "%~dp0DockerDesktopInstaller.exe" install --quiet --accept-license
        if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
            echo   [OK] Docker Desktop 安装成功
        ) else (
            echo   [警告] 安装可能未完成，请手动运行 DockerDesktopInstaller.exe
            pause
            exit /b 1
        )
    ) else (
        echo   [错误] 未找到 DockerDesktopInstaller.exe
        echo   请从以下地址下载并放到此脚本同目录:
        echo   https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe
        pause
        exit /b 1
    )
)
echo.

:: ===== Phase 3: 启动 Docker Engine =====
echo [步骤 3] 检查 Docker Engine...
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" info >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] Docker Engine 正在运行
) else (
    echo   Docker Engine 未运行，启动 Docker Desktop...
    if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        echo   等待 Docker Engine 就绪（最多120秒）...
        set WAITED=0
        :WAIT_DOCKER
        timeout /t 5 /nobreak >nul
        set /a WAITED+=5
        "C:\Program Files\Docker\Docker\resources\bin\docker.exe" info >nul 2>&1
        if %errorLevel% equ 0 (
            echo   [OK] Docker Engine 已就绪
            goto DOCKER_READY
        )
        if %WAITED% lss 120 (
            echo   已等待 %WAITED% 秒...
            goto WAIT_DOCKER
        )
        echo   [错误] Docker Engine 启动超时
        echo   请手动启动 Docker Desktop，等待右下角图标变绿后重新运行此脚本
        pause
        exit /b 1
    )
)
:DOCKER_READY
echo.

:: ===== Phase 4: 部署 Dify =====
echo [步骤 4] 部署 Dify 社区版...
echo.

:: 找到 Git Bash
set BASH_PATH=
if exist "C:\Program Files\Git\bin\bash.exe" (
    set "BASH_PATH=C:\Program Files\Git\bin\bash.exe"
) else (
    where bash.exe >nul 2>&1 && for /f "delims=" %%i in ('where bash.exe') do set "BASH_PATH=%%i"
)

if not defined BASH_PATH (
    echo   [错误] 未找到 Git Bash
    echo   请安装 Git for Windows: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo   使用 Bash: %BASH_PATH%
echo   运行部署脚本...
echo.
"%BASH_PATH%" -c "cd '%~dp0' && bash deploy-dify.sh"

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo.
echo   下一步:
echo   1. 浏览器访问 http://localhost:3000
echo   2. 注册管理员账号
echo   3. 配置 LLM 模型
echo   4. 创建知识库
echo   5. 创建 Agent 应用
echo.
echo   详细指南: 打开 setup-guide.html
echo ========================================
echo.
pause
