@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto BAD_DIRECTORY
call "%~dp0_find_python.bat"
if errorlevel 1 goto NO_PYTHON
%CALIX_PYTHON% -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto INSTALL_FAILED
echo.
echo [OK] Dependencies installed.
pause
exit /b 0
:BAD_DIRECTORY
echo [ERROR] Could not open the application folder.
goto FAILED
:NO_PYTHON
echo [ERROR] Python not found.
goto FAILED
:INSTALL_FAILED
echo [ERROR] Dependency installation failed. See the messages above.
goto FAILED
:FAILED
pause
exit /b 1
