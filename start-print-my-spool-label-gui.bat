@echo off
setlocal

cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo FEHLER: Python wurde nicht gefunden.
        echo Fuehre zuerst install-print-my-spool-label.bat aus.
        pause
        exit /b 1
    )
    set "PYTHON=py"
)

echo Starte PrintMySpoolLabel GUI ...
%PYTHON% ".\src\app.py"
if errorlevel 1 (
    echo.
    echo Die GUI wurde mit einem Fehler beendet.
    echo Falls Abhaengigkeiten fehlen, fuehre install-print-my-spool-label.bat aus.
    pause
    exit /b 1
)

endlocal
exit /b 0
