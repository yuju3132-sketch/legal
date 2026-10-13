@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The project Python environment is missing.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\automation.py remove
set "LEGAL_EXIT=%ERRORLEVEL%"
pause
exit /b %LEGAL_EXIT%
