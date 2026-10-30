@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto FAILED
call "%~dp0_find_python.bat"
if errorlevel 1 goto FAILED
%CALIX_PYTHON% "%~dp0main.py" %*
exit /b %ERRORLEVEL%
:FAILED
echo [ERROR] See README.md for source setup.
pause
exit /b 1
