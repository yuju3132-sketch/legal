@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please complete setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\automation.py install
set "LEGAL_EXIT=%ERRORLEVEL%"
if not "%LEGAL_EXIT%"=="0" echo Automatic scheduling was not completed. Check the messages above.
pause
exit /b %LEGAL_EXIT%
