@echo off
cd /d "%~dp0"
call "%~dp0START_CHROME_DIRECT.cmd"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if exist "%VPY%" (
  "%VPY%" "%~dp0system\cdp_login_keepalive.py" --open-login-page --interval 180
  exit /b %ERRORLEVEL%
)
python "%~dp0system\cdp_login_keepalive.py" --open-login-page --interval 180
exit /b %ERRORLEVEL%
