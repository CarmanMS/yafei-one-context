@echo off
chcp 65001 >nul

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要管理员权限，正在自动提权...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================
echo   Docker 修复脚本（管理员模式）
echo ========================================
echo.

echo [1/5] 添加 Windows Defender 排除项...
powershell -Command "Add-MpPreference -ExclusionPath 'C:\Users\wucha\.docker'" 2>nul
powershell -Command "Add-MpPreference -ExclusionPath 'C:\Program Files\Docker'" 2>nul
powershell -Command "Add-MpPreference -ExclusionProcess 'Docker Desktop.exe'" 2>nul
powershell -Command "Add-MpPreference -ExclusionProcess 'com.docker.backend.exe'" 2>nul
powershell -Command "Add-MpPreference -ExclusionProcess 'docker.exe'" 2>nul
echo   已添加排除项
echo.

echo [2/5] 清理旧的 Docker 配置...
del /f /q "C:\Users\wucha\.docker\config.json" 2>nul
del /f /q "C:\Users\wucha\.docker\daemon.json" 2>nul
del /f /q "C:\Users\wucha\.docker\windows-daemon.json" 2>nul
del /f /q "C:\Users\wucha\.docker\*.tmp*" 2>nul
echo   已清理
echo.

echo [3/5] 结束残留 Docker 进程...
taskkill /F /IM "Docker Desktop.exe" 2>nul
taskkill /F /IM "com.docker.backend.exe" 2>nul
taskkill /F /IM "docker.exe" 2>nul
timeout /t 3 /nobreak >nul
echo   已清理
echo.

echo [4/5] 修复目录权限...
icacls "C:\Users\wucha\.docker" /grant "wucha:(OI)(CI)(F)" /T 2>nul
echo   已修复
echo.

echo [5/5] 启动 Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo   已启动，等待 Engine 初始化（需要 1-3 分钟）...
echo.

echo 正在等待 Docker Engine 就绪...
set "DOCKER=C:\Program Files\Docker\Docker\resources\bin\docker.exe"
set /a count=0

:CHECK_LOOP
set /a count+=1
"%DOCKER%" info >nul 2>&1
if %errorlevel% equ 0 goto :READY
if %count% geq 36 goto :TIMEOUT
echo   等待中... %count%/36
timeout /t 5 /nobreak >nul
goto :CHECK_LOOP

:READY
echo.
echo ========================================
echo   ✅ Docker Engine 启动成功！
echo ========================================
"%DOCKER%" --version
"%DOCKER%" compose version
echo.
echo 可以关闭此窗口，回到 WorkBuddy 继续部署 Dify。
echo.
pause
exit /b

:TIMEOUT
echo.
echo ========================================
echo   ⏳ Docker Engine 还在初始化中
echo ========================================
echo Docker Desktop 窗口可能还在启动。
echo 请检查系统托盘右下角 Docker 图标是否变绿。
echo 如果图标已绿，请回到 WorkBuddy 告诉我"Docker 好了"。
echo.
echo 如果 Docker Desktop 窗口有错误提示，
echo 请截图发给我。
echo.
pause
exit /b
