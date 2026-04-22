@echo off
cd /d "%~dp0"
.\.venv-portal\Scripts\python.exe packet_lab\replay_lab_ui.py
pause
