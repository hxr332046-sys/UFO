@echo off
REM 仅本机逆开发自测：绕过 TLS 证书错误（含 ERR_CERT_DATE_INVALID），可进入 6087 等过期证书页。
REM 不安全：勿作日常浏览器。若已开 Chrome Dev，请先全部关掉再双击本文件。
cd /d "%~dp0"
set "V=%~dp0.venv-portal\Scripts\python.exe"
if not exist "%V%" (
  echo 缺少 .venv-portal
  exit /b 1
)
"%V%" "%~dp0scripts\launch_browser.py" --no-proxy --ignore-cert-errors
