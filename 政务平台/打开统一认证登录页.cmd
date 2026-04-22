@echo off
REM 在已运行的 Chrome Dev（CDP 9225）当前页签跳转到 #/login/authPage；若未开浏览器会先启动。
cd /d "%~dp0"
set "VPY=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%VPY%" (
  echo ERROR: 缺少 .venv-portal
  pause
  exit /b 1
)
"%VPY%" "%~dp0scripts\launch_browser.py" --no-proxy 2>nul
REM 刚启动浏览器时给首页与 TLS 一点时间，再跳登录页，减轻风控
timeout /t 5 /nobreak >nul
"%VPY%" "%~dp0system\cdp_open_login_page.py"
echo.
echo 若浏览器已显示统一认证登录页，请完成登录。
pause
