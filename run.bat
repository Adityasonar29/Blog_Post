@echo off
cd /d "%~dp0"
echo Starting Fieldnotes at http://127.0.0.1:5000
py app.py
if errorlevel 1 (
  echo.
  echo Fieldnotes could not start. Keep this window open and read the error above.
  pause
)
