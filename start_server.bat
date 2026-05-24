@echo off
echo ========================================
echo   AIML Attendance System - Starting...
echo ========================================
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
) else (
    echo [WARN] No .venv found, using system Python
)

echo [OK] Starting server on port 8002...
echo [OK] Open browser: http://localhost:8002/dashboard
echo.
echo Press Ctrl+C to stop the server.
echo ========================================

uvicorn backend.main:app --host 0.0.0.0 --port 8002 --reload

pause
