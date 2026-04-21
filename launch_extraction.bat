@echo off
echo Starting EHR Data Extraction System...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check if in the right directory
if not exist "backend\requirements.txt" (
    echo Please run this script from the EHRData directory
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

REM Initialize database
echo Initializing database...
python -m app.init_db
if errorlevel 1 (
    echo Failed to initialize database
    pause
    exit /b 1
)

REM Start services
echo Starting services...
echo 1. PDF Watcher Service (monitors folders for new PDFs)
echo 2. API Server (localhost:8000)
echo 3. Frontend Dashboard (localhost:3000)
echo.

REM Start PDF watcher in background
start cmd /k "python -m app.services.pdf_watcher"

REM Start API server
start cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo.
echo Services started!
echo - PDF Watcher: Monitoring folders for new PDFs
echo - API Server: http://localhost:8000
echo - API Docs: http://localhost:8000/docs
echo.
echo Press any key to open the dashboard...
pause >nul

REM Open browser to dashboard
start http://localhost:8000