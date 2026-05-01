@echo off
cd /d "%~dp0"

REM Check Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.11+ and add it to PATH.
    pause
    exit /b 1
)

REM Install Python dependencies if needed
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

pip install -q -r requirements.txt

echo Starting TARP Dashboard...
python backend\main.py
pause
