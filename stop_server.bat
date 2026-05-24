@echo off
echo Stopping AIML Attendance Server...
taskkill /f /im uvicorn.exe 2>nul
taskkill /f /im python.exe /fi "WINDOWTITLE eq uvicorn*" 2>nul
echo Server stopped.
pause
