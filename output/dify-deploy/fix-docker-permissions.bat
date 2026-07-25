@echo off
chcp 65001 >nul 2>&1

:: 自动提权
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c %~dpnx0' -Verb RunAs"
    exit /b
)

title 修复 Docker Desktop 权限问题
echo.
echo ========================================
echo   修复 Docker Desktop 文件权限问题
echo   原因: Windows Defender 实时保护锁文件
echo ========================================
echo.

echo [1/4] 添加 Windows Defender 排除项...
powershell -Command "Add-MpPreference -ExclusionPath 'C:\Users\wucha\.docker'"
powershell -Command "Add-MpPreference -ExclusionPath 'C:\Users\wucha\AppData\Local\Docker'"
powershell -Command "Add-MpPreference -ExclusionProcess 'com.docker.backend.exe'"
powershell -Command "Add-MpPreference -ExclusionProcess 'Docker Desktop.exe'"
echo   完成
echo.

echo [2/4] 清理旧的 Docker 配置文件...
del /f /q "C:\Users\wucha\.docker\config.json" 2>nul
del /f /q "C:\Users\wucha\.docker\daemon.json" 2>nul
del /f /q "C:\Users\wucha\.docker\windows-daemon.json" 2>nul
del /f /q "C:\Users\wucha\.docker\*.tmp*" 2>nul
echo   完成
echo.

echo [3/4] 结束残留 Docker 进程...
taskkill /F /IM "Docker Desktop.exe" 2>nul
taskkill /F /IM "com.docker.backend.exe" 2>nul
timeout /t 3 /nobreak >nul
echo   完成
echo.

echo [4/4] 启动 Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo   Docker Desktop 正在启动，请等待 1-3 分钟...
echo.

echo ========================================
echo   修复完成！
echo.
echo   请等待 Docker Desktop 完全启动后，
echo   然后回到对话中告诉我 "Docker 已就绪"
echo ========================================
echo.
pause
