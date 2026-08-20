@echo off
setlocal

cd /d "%~dp0"

echo Aktualisiere PrintMySpoolLabel ...
git pull
if errorlevel 1 (
    echo.
    echo Git pull ist fehlgeschlagen.
    pause
    exit /b 1
)

echo Starte PrintMySpoolLabel ...
set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3.12"
)
if not defined PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON=python"
    )
)
if not defined PYTHON (
    echo FEHLER: Python 3.12 wurde nicht gefunden. Fuehre zuerst die Installation aus.
    pause
    exit /b 1
)

%PYTHON% ".\src\app.py"

if errorlevel 1 (
    echo.
    echo Die Anwendung wurde mit einem Fehler beendet.
    pause
)

endlocal
