@echo off
echo =======================================
echo   AltusFlow Outbound Hunter
echo =======================================
echo.
echo Starting Flask app on http://localhost:5000
echo Reddit scanner runs daily at 6:00 AM
echo Press Ctrl+C to stop
echo.

cd /d "C:\Users\ghhoc\Projects\AltusFlow\outbound-hunter"

if not exist .env.local (
    echo WARNING: .env.local not found
    echo Open .env.local and paste your API keys
    echo.
)

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)

set USE_POD_ORCHESTRATOR=true
set FLASK_ENV=production
set SCAN_CRON_HOUR=6
set SCAN_CRON_MINUTE=0
set NO_AUTH=true

start "" "http://localhost:5000/dashboard"
python app.py
pause
