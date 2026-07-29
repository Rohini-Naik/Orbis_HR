@echo off
REM Orbis - start the backend and frontend together (Windows).
REM Shares its implementation with Unix via start.py.
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" start.py %*
    goto :end
)

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 start.py %*
    goto :end
)

python start.py %*

:end
