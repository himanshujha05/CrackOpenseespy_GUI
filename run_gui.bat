@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
python gui_wsl.py
pause
