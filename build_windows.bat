@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto BAD_DIRECTORY
call "%~dp0_find_python.bat"
if errorlevel 1 goto NO_PYTHON
%CALIX_PYTHON% "%~dp0tools\check_runtime_security.py"
if errorlevel 1 goto BUILD_FAILED
%CALIX_PYTHON% -m pip install --only-binary=:all: -r "%~dp0requirements-build.txt"
if errorlevel 1 goto BUILD_FAILED
%CALIX_PYTHON% -B "%~dp0tools\prepare_assets.py"
if errorlevel 1 goto BUILD_FAILED
set "CALIX_DEBUG="
set "CALIX_OUTPUT=%~dp0..\Calix-builds"
%CALIX_PYTHON% -m PyInstaller --noconfirm --clean --distpath "%CALIX_OUTPUT%" --workpath "%CALIX_OUTPUT%\.build-cache" "%~dp0Calix.spec"
if errorlevel 1 goto BUILD_FAILED
%CALIX_PYTHON% "%~dp0tools\check_bundle.py" "%CALIX_OUTPUT%\Calix 1.0.9-r2"
if errorlevel 1 goto BUILD_FAILED
echo.
echo [OK] EXE: "%CALIX_OUTPUT%\Calix 1.0.9-r2\Calix.exe"
pause
exit /b 0
:BAD_DIRECTORY
echo [ERROR] Could not open the application folder.
goto FAILED
:NO_PYTHON
echo [ERROR] Python 3.14.10 required.
goto FAILED
:BUILD_FAILED
echo [ERROR] EXE build failed. See the messages above.
goto FAILED
:FAILED
pause
exit /b 1
