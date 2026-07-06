@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo First-time setup: creating virtual environment...
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" main.py
