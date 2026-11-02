@echo off
REM ============================================================
REM  ExpoHub 一键停止（Windows）
REM  结束后端 :8002 与前端 :5173 上的 ExpoHub 进程
REM ============================================================
chcp 65001 >nul 2>nul
setlocal
cd /d "%~dp0"

set "PSEXE=powershell.exe"
where pwsh.exe >nul 2>nul && set "PSEXE=pwsh.exe"

"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_all.ps1" %*
echo.
pause
endlocal & exit /b 0
