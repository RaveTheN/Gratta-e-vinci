@echo off
echo ===============================================
echo Gratta-e-Vinci Automation GUI Setup
echo ===============================================
echo.

echo Creating virtual environment...
python -m venv .venv

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Installing required packages...
.venv\Scripts\pip.exe install -r requirements.txt

echo.
echo ===============================================
echo Setup completed successfully!
echo ===============================================
echo.
echo To run the application:
echo 1. Double-click "run_gui.bat"
echo 2. Or run: .venv\Scripts\python.exe gratta_e_vinci_gui.py
echo.
echo Features:
echo - Real-time mouse coordinate display
echo - Configurable game settings
echo - Automated gameplay with escape key stop
echo - Test mode for safe testing
echo - Settings save/load functionality
echo.
pause
