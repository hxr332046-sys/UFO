@echo off
REM 最简流程：先 打开登录器.cmd 在 Chrome Dev 里手动登录 9087，再运行本脚本写入 runtime_auth_headers.json
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal，请先运行 scripts\setup_portal_env.ps1
  pause
  exit /b 1
)
echo 确认已在 CDP Chrome 中完成登录后按任意键同步...
pause
"%VPY%" "%~dp0packet_lab\sync_runtime_auth_from_browser_cdp.py"
set ERR=%ERRORLEVEL%
if not "%ERR%"=="0" pause
exit /b %ERR%
