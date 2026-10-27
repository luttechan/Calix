@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto BAD_DIRECTORY
call "%~dp0_find_python.bat"
if errorlevel 1 goto NO_PYTHON
%CALIX_PYTHON% -m pip install --only-binary=:all: -r "%~dp0requirements-build.txt"
if errorlevel 1 goto BUILD_FAILED
set "CALIX_DEBUG=1"
%CALIX_PYTHON% -m PyInstaller --noconfirm --clean "%~dp0Calix.spec"
if errorlevel 1 goto BUILD_FAILED
echo.
echo [OK] Debug EXE: dist\Calix-Debug-1.0.1\Calix-Debug.exe
pause
exit /b 0
:BAD_DIRECTORY
echo [ERROR] Could not open the application folder.
goto FAILED
:NO_PYTHON
echo [ERROR] Python not found.
goto FAILED
:BUILD_FAILED
echo [ERROR] Debug EXE build failed. See the messages above.
goto FAILED
:FAILED
pause
exit /b 1
