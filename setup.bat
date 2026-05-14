@echo off
cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python is not installed or not found.
    echo Please install it from: https://www.python.org/downloads/
    echo During installation, make sure to tick "Add Python to PATH".
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Setup failed. Please ask Ananth for help.
    echo.
    pause
    exit /b 1
)

echo.
echo Setup complete! You can now double-click start.bat to launch the dashboard.
echo.
pause
