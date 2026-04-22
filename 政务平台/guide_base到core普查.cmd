@echo off
REM guide/base（S08）按 entType 分段普查 → core；默认 1100、类人节奏；不点「云提交」
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal
  pause
  exit /b 1
)
"%VPY%" "%~dp0system\cdp_guide_base_to_core_census.py" %*
echo.
echo 记录: dashboard\data\records\cdp_guide_base_to_core_census_latest.json
pause
