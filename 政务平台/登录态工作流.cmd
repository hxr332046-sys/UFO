@echo off
setlocal
cd /d "%~dp0"

set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if exist "%VPY%" (
  set "PY=%VPY%"
 ) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: 缺少 .venv-portal 且系统中找不到 python
    pause
    exit /b 1
  )
  set "PY=python"
)

"%PY%" "%~dp0system\auth_runtime_workflow.py" --repair-on-fail
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" pause
exit /b %ERR%
