@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto BAD_DIRECTORY
call "%~dp0_find_python.bat"
if errorlevel 1 goto NO_PYTHON
%CALIX_PYTHON% -u -X faulthandler "%~dp0main.py"
set "RC=%ERRORLEVEL%"
echo.
echo [INFO] Exit code: %RC%
echo [INFO] Log: "%LOCALAPPDATA%\Calix\logs\app.log"
pause
exit /b %RC%
:BAD_DIRECTORY
echo [ERROR] Could not open the application folder.
goto FAILED
:NO_PYTHON
echo [ERROR] Python not found.
goto FAILED
:FAILED
pause
exit /b 1
