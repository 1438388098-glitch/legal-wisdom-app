@echo off
set PY=C:\Users\20579\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PY%" (
    echo Error: Python 3.13 not found at %PY%
    echo Please reinstall Python 3.13 or update the path in run.bat
    pause
    exit /b 1
)
cd /d "%~dp0"
"%PY%" main.py
echo Exit code: %ERRORLEVEL%
pause
