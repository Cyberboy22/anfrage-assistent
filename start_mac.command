#!/bin/bash
# Anfrage-Assistent starten (macOS / Linux). Doppelklick oder: bash start_mac.command
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 wurde nicht gefunden."
  echo "Bitte installieren: https://www.python.org/downloads/ (oder: xcode-select --install)"
  read -r -p "Enter zum Schließen …"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Erster Start: Ich richte alles ein, das dauert 1–2 Minuten …"
  python3 -m venv .venv || { echo "Fehler beim Anlegen der Umgebung."; exit 1; }
fi
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt || { echo "Fehler bei der Installation."; exit 1; }

echo
echo "Der Anfrage-Assistent startet gleich im Browser: http://localhost:8501"
echo "Zum Beenden: Ctrl+C oder dieses Fenster schließen."
echo
( sleep 4; open "http://localhost:8501" 2>/dev/null || xdg-open "http://localhost:8501" 2>/dev/null ) &
.venv/bin/python -m streamlit run app.py
