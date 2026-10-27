@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "%~dp0app\Calix.exe" goto MISSING
start "" /D "%~dp0app" "%~dp0app\Calix.exe"
exit /b 0
:MISSING
echo Download the Windows ZIP from https://github.com/luttechan/Calix/releases
pause
exit /b 1
