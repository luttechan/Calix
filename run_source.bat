@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto FAILED
where pnpm >nul 2>nul
if errorlevel 1 goto FAILED
cd /d "%~dp0desktop"
call pnpm tauri dev
exit /b %ERRORLEVEL%
:FAILED
echo [ERROR] See README.md for source setup.
pause
exit /b 1
