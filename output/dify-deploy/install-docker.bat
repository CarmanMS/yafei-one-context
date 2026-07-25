@echo off
chcp 65001 >nul 2>&1
echo.
echo ========================================
echo   正在安装 Docker Desktop
echo   请在 UAC 提示中点击"是"
echo ========================================
echo.
"%~dp0DockerDesktopInstaller.exe" install --quiet --accept-license
echo.
echo 安装退出码: %errorLevel%
if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    echo [成功] Docker Desktop 已安装
) else (
    echo [注意] 安装可能未完成，请检查上方信息
)
echo.
pause
