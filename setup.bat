@echo off
REM Orbis setup - Windows.
REM The real logic lives in setup.py so Windows and Unix share one implementation.
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 setup.py %*
    goto :end
)

where python >nul 2>&1
if %errorlevel%==0 (
    python setup.py %*
    goto :end
)

echo Python 3.11+ is required but was not found on PATH.
echo Install it from https://www.python.org/downloads/ ^(tick "Add Python to PATH"^),
echo then re-run setup.bat
exit /b 1

:end
if %errorlevel% neq 0 (
    echo.
    echo Setup did not complete. Fix the error above and run setup.bat again.
)
pause
