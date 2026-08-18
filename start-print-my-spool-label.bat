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
where python >nul 2>&1
if not errorlevel 1 (
    python ".\src\app.py"
) else (
    py ".\src\app.py"
)

if errorlevel 1 (
    echo.
    echo Die Anwendung wurde mit einem Fehler beendet.
    pause
)

endlocal
