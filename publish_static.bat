@echo off
cd /d "%~dp0"
py export_static.py
if errorlevel 1 (
  echo.
  echo Static export failed. Check MongoDB and your .env settings.
  exit /b 1
)
echo.
echo Static site updated in github-pages\
echo Commit it with: git add github-pages export_static.py publish_static.bat requirements.txt
