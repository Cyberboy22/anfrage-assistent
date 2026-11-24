@echo off
chcp 65001 >nul
title Anfrage-Assistent
cd /d "%~dp0"

rem --- Python suchen ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python wurde nicht gefunden.
    echo Bitte Python 3.10 oder neuer von https://www.python.org/downloads/ installieren
    echo und dabei "Add Python to PATH" anhaken. Danach diese Datei erneut starten.
    pause
    exit /b 1
)

rem --- Einmalig: virtuelle Umgebung + Pakete ---
if not exist ".venv\Scripts\python.exe" (
    echo Erster Start: Ich richte alles ein, das dauert 1-2 Minuten ...
    %PY% -m venv .venv || (echo Fehler beim Anlegen der Umgebung. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo Fehler bei der Installation. & pause & exit /b 1)

echo.
echo Der Anfrage-Assistent startet gleich im Browser: http://localhost:8501
echo Zum Beenden dieses Fenster schliessen.
echo.
start "" /b ".venv\Scripts\python.exe" -c "import time, webbrowser; time.sleep(4); webbrowser.open('http://localhost:8501')"
".venv\Scripts\python.exe" -m streamlit run app.py
pause
