@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
call "%~dp0_find_python.bat"
if errorlevel 1 exit /b 1
%CALIX_PYTHON% -m pip install --only-binary=:all: -r requirements-build.txt brotli==1.2.1
if errorlevel 1 exit /b 1
%CALIX_PYTHON% desktop\tools\prepare_web_assets.py
if errorlevel 1 exit /b 1
%CALIX_PYTHON% desktop\tools\build_engine.py
if errorlevel 1 exit /b 1
pushd desktop
call pnpm install --frozen-lockfile
if errorlevel 1 goto FAILED
call pnpm test
if errorlevel 1 goto FAILED
call pnpm tauri build
if errorlevel 1 goto FAILED
popd
%CALIX_PYTHON% desktop\tools\package_desktop.py
exit /b %ERRORLEVEL%
:FAILED
popd
exit /b 1
