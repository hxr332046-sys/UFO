@echo off
REM 验收线 L1：02_4 + 1100，guide/base → core → 材料第一屏（类人节奏；不点云提交）
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal
  pause
  exit /b 1
)
"%VPY%" "%~dp0system\cdp_acceptance_line_02_4_1100.py" %*
echo.
echo 记录: dashboard\data\records\acceptance_line_02_4_1100_latest.json
echo 退出码 0=五项验收全过；1=partial 或 fail；2=无 CDP
pause
