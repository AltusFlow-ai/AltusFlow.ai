@echo off
cd /d "%~dp0"

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo Node.js not found. Install it with:
    echo   winget install OpenJS.NodeJS
    echo Then open a new terminal and re-run this script.
    pause
    exit /b 1
)

if not exist node_modules (
    echo Installing dependencies...
    npm install
    if %errorlevel% neq 0 ( echo npm install failed. & pause & exit /b 1 )
)

echo Building dashboard...
npm run build
if %errorlevel% neq 0 ( echo Build failed. & pause & exit /b 1 )

echo.
echo Done. Dashboard available at /dashboard once Flask is running.
pause
