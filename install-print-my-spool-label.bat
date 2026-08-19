@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo PrintMySpoolLabel - Installation
echo ========================================
echo.

call :ensure_tool git Git.Git Git
if errorlevel 1 goto :failed

set "PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        call :ensure_tool python Python.Python.3.12 Python
        if errorlevel 1 goto :failed
        set "PYTHON=python"
    ) else (
        set "PYTHON=py"
    )
)

call :ensure_tool npm.cmd OpenJS.NodeJS.LTS Node.js
if errorlevel 1 goto :failed

if defined NEEDS_RESTART (
    echo.
    echo Eine Systemkomponente wurde installiert.
    echo Das Installationsscript muss neu gestartet werden, damit die neuen PATH-Eintraege aktiv sind.
    choice /M "Script jetzt neu starten"
    if errorlevel 2 goto :failed
    start "" "%~f0"
    endlocal
    exit /b 0
)

echo Installiere Python-Abhaengigkeiten ...
%PYTHON% -m pip install --requirement "%~dp0requirements.txt"
if errorlevel 1 (
    echo FEHLER: Python-Abhaengigkeiten konnten nicht installiert werden.
    goto :failed
)

echo.
echo Installiere niimblue-node ...
npm.cmd install --global @mmote/niimblue-node
if errorlevel 1 (
    echo FEHLER: niimblue-node konnte nicht installiert werden.
    goto :failed
)

echo.
echo Installation erfolgreich abgeschlossen.
echo Starte die Anwendung mit start-print-my-spool-label.bat.
pause
endlocal
exit /b 0

:failed
echo.
echo Installation abgebrochen.
pause
endlocal
exit /b 1

:ensure_tool
where "%~1" >nul 2>&1
if not errorlevel 1 exit /b 0

echo.
echo %~3 wurde nicht gefunden.
where winget >nul 2>&1
if errorlevel 1 (
    echo FEHLER: winget ist nicht verfuegbar. Installiere %~3 manuell und starte dieses Script erneut.
    exit /b 1
)

choice /M "%~3 jetzt ueber winget installieren"
if errorlevel 2 (
    echo Installation von %~3 wurde abgelehnt.
    exit /b 1
)

winget install --id "%~2" --exact --source winget --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo FEHLER: %~3 konnte nicht installiert werden.
    exit /b 1
)
set "NEEDS_RESTART=1"
exit /b 0
