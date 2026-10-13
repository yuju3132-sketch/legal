@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3 --version >nul 2>&1
if errorlevel 1 goto fallback
py -3 -m venv .venv
if errorlevel 1 goto error
goto install
:fallback
python --version >nul 2>&1
if errorlevel 1 goto missing
python -m venv .venv
if errorlevel 1 goto error
:install
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required'"
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
".venv\Scripts\python.exe" scripts\manage.py init
if errorlevel 1 goto error
echo Setup complete. Double-click run_app.bat.
pause
exit /b 0
:missing
echo Install Python 3.10+ from python.org and enable Add Python to PATH.
:error
echo Setup failed. Check the messages above. Database files are preserved.
pause
exit /b 1
