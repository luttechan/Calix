@echo off
if exist "%~dp0.venv\Scripts\python.exe" (
  set CALIX_PYTHON="%~dp0.venv\Scripts\python.exe"
  exit /b 0
)
py -3.14 -c "import sys; assert sys.version_info[:3] == (3,14,10)" >nul 2>nul
if not errorlevel 1 (
  set "CALIX_PYTHON=py -3.14"
  exit /b 0
)
python -c "import sys; assert sys.version_info[:3] == (3,14,10)" >nul 2>nul
if not errorlevel 1 (
  set "CALIX_PYTHON=python"
  exit /b 0
)
exit /b 1
