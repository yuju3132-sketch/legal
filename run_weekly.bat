@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\manage.py weekly
set "LEGAL_EXIT=%ERRORLEVEL%"
if not "%LEGAL_EXIT%"=="0" echo Check logs\research.log. Exit code %LEGAL_EXIT% indicates failure or partial collection.
pause
exit /b %LEGAL_EXIT%
