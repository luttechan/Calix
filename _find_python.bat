@echo off
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0tools\check_runtime_security.py" >nul 2>nul
  if not errorlevel 1 (
    set CALIX_PYTHON="%~dp0.venv\Scripts\python.exe"
    exit /b 0
  )
)
py -3.14 "%~dp0tools\check_runtime_security.py" >nul 2>nul
if not errorlevel 1 (
  set "CALIX_PYTHON=py -3.14"
  exit /b 0
)
python "%~dp0tools\check_runtime_security.py" >nul 2>nul
if not errorlevel 1 (
  set "CALIX_PYTHON=python"
  exit /b 0
)
echo [ERROR] Python 3.14.10 with a current OpenSSL runtime is required.
exit /b 1
