@echo off
REM 不跳门户：从当前 9087 icpsp 页签续跑主循环（适合已在 core / 半道办件）
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal
  pause
  exit /b 1
)
"%VPY%" "%~dp0system\packet_chain_portal_from_start.py" --resume-current --assets "%~dp0config\rehearsal_assets.json" -o "%~dp0dashboard\data\records\framework_rehearsal_resume_latest.json" --iter-latest
echo.
echo JSON: dashboard\data\records\framework_rehearsal_resume_latest.json
pause
