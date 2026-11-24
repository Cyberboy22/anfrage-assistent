"""Klickt die Oberfläche einmal komplett durch."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_startet_und_analysiert():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.selectbox(key="beispiel_wahl").select("Energieausweis für Mehrfamilienhaus – dringend").run()
    at.button[0].click().run()
    assert not at.exception
    metriken = {m.label: m.value for m in at.metric}
    assert metriken["Priorität"] == "🔴 hoch"
    entwurf = next(t for t in at.text_area if t.label == "Text (bearbeitbar)").value
    assert entwurf.startswith("Guten Tag Thomas Becker,")


def test_leere_anfrage_gibt_hinweis():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert any("Bitte zuerst" in w.value for w in at.warning)
