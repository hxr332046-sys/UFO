@echo off
REM 从头 portal 走设立登记至「云提交」文案停点；--assets 注入身份证+模拟件；不点云提交
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal
  pause
  exit /b 1
)
"%VPY%" "%~dp0system\packet_chain_portal_from_start.py" --assets "%~dp0config\rehearsal_assets.json" --iter-latest -o "%~dp0dashboard\data\records\framework_rehearsal_run_latest.json"
echo.
echo JSON: dashboard\data\records\framework_rehearsal_run_latest.json
echo MD:   dashboard\data\records\framework_rehearsal_latest.md
pause
