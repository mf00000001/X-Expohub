@echo off
REM ============================================================
REM  ExpoHub 一键启动（Windows）
REM  双击本文件即可：自动装依赖 -> 起后端 :8002 -> 起前端 :5173 -> 开浏览器
REM
REM  可选参数（在命令行里追加）：
REM    -NoBrowser              不自动打开浏览器
REM    -Reload                 后端热重载
REM    -Background             后台启动，日志写入 logs\
REM    -BindHost 0.0.0.0       允许局域网/手机访问
REM    -BackendPort 8002 -FrontendPort 5173
REM ============================================================
chcp 65001 >nul 2>nul
setlocal
cd /d "%~dp0"

set "PSEXE=powershell.exe"
where pwsh.exe >nul 2>nul && set "PSEXE=pwsh.exe"

"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_all.ps1" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo 启动未成功（退出码 %RC%），按任意键关闭窗口。
  pause
)
endlocal & exit /b %RC%
