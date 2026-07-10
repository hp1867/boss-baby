@echo off
cd /d "%~dp0"
rem venv lives OUTSIDE OneDrive - syncing it makes Python unusably slow
set VENV=%USERPROFILE%\.venvs\bossbaby
if not exist "%VENV%\Scripts\pythonw.exe" (
    echo First-time setup: creating virtual environment...
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv "%VENV%"
    "%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" "%VENV%\Scripts\pythonw.exe" main.py
