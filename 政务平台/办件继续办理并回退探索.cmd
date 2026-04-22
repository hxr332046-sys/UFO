@echo off
REM 办件进度 -> 指定行「继续办理」-> 多次「上一步」探路（不点云提交）；默认匹配企业名含「食品市」的测试行
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal
  pause
  exit /b 1
)
"%VPY%" "%~dp0system\cdp_resume_draft_explore.py" --name-substr "食品市" --max-back 15
echo.
echo 记录: dashboard\data\records\cdp_resume_draft_explore_latest.json
pause
