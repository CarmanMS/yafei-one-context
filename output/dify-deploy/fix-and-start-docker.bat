@echo off
chcp 65001 >nul
echo ========================================
echo   Docker 权限修复 + 启动脚本
echo ========================================
echo.

echo [1/4] 添加 Windows Defender 排除项...
powershell -Command "Add-MpPreference -ExclusionPath 'C:\Users\wucha\.docker' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionPath 'C:\Program Files\Docker' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess 'Docker Desktop.exe' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess 'com.docker.backend.exe' -ErrorAction SilentlyContinue"
echo Done.
echo.

echo [2/4] 修复 .docker 目录权限...
icacls "C:\Users\wucha\.docker\config.json" /grant "wucha:(F)" /T 2>nul
icacls "C:\Users\wucha\.docker\daemon.json" /grant "wucha:(F)" /T 2>nul
icacls "C:\Users\wucha\.docker" /grant "wucha:(F)" /T 2>nul
echo Done.
echo.

echo [3/4] 结束残留 Docker 进程...
taskkill /F /IM "Docker Desktop.exe" 2>nul
taskkill /F /IM "com.docker.backend.exe" 2>nul
timeout /t 3 /nobreak >nul
echo Done.
echo.

echo [4/4] 启动 Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo Docker Desktop 已启动，等待 Engine 初始化...
echo.

echo 请保持此窗口打开，等待 60 秒后自动检查状态...
timeout /t 60 /nobreak >nul

echo 正在检查 Docker Engine 状态...
"C:\Program Files\Docker\Docker\resources\bin\docker.exe" info >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   ✅ Docker Engine 启动成功！
    echo ========================================
    "C:\Program Files\Docker\Docker\resources\bin\docker.exe" --version
    "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose version
    echo.
    echo 可以继续部署 Dify 了！
) else (
    echo.
    echo ========================================
    echo   ❌ Docker Engine 尚未就绪
    echo ========================================
    echo 请检查 Docker Desktop 窗口是否有错误提示。
    echo 可能需要重启电脑后再试。
)
echo.
pause
