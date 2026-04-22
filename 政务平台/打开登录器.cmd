@echo off
REM 独立登录环境：Chrome Dev（见 config\browser.json 的 executable）+ CDP + 9087 门户，无系统代理
REM 手动登录完成后，再运行 手动登录后同步登录态.cmd 生成 packet_lab\out\runtime_auth_headers.json
cd /d "%~dp0"
call "%~dp0START_CHROME_DIRECT.cmd"
