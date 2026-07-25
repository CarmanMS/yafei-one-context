@echo off
chcp 65001 >nul 2>&1

:: 自动提权
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c %~dpnx0' -Verb RunAs"
    exit /b
)

title 启用 WSL2 和虚拟化功能
echo.
echo ========================================
echo   启用 WSL2 和虚拟化功能
echo ========================================
echo.

echo [1/2] 启用 WSL 功能...
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
echo.

echo [2/2] 启用虚拟机平台...
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
echo.

echo ========================================
echo   功能已启用！需要重启电脑才能生效。
echo.
echo   重启后：
echo   1. Docker Desktop 会自动启动
echo   2. 或双击 "一键搭建.bat" 继续部署 Dify
echo ========================================
echo.
set /p RESTART=是否立即重启？(y/n):
if /i "%RESTART%"=="y" (
    shutdown /r /t 5 /c "启用 WSL2 后重启"
)
pause
