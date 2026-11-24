"""Gesamter Ablauf inkl. KI – mit einer simulierten KI, damit die Tests ohne Internet laufen."""

import json

from conftest import beispiel

from assistent.llm import KIEinstellungen, KIFehler
from assistent.pipeline import analysiere

OLLAMA = KIEinstellungen("ollama", modell="test-modell")


def test_ohne_ki_vollstaendige_anfrage_braucht_keine_rueckfragen():
    e = analysiere(beispiel("01"))
    assert e.rueckfragen == []
    assert e.betreff.startswith("AW: Anfrage Sanierungsfahrplan")
    assert "Guten Tag Sabine Krüger," in e.antwort
    assert "Baujahr 1972" in e.antwort
    assert "Ihr Team der Energieberatung" in e.antwort


def test_fehlende_angaben_werden_zu_rueckfragen():
    e = analysiere(beispiel("03"))
    assert "baujahr" in e.fehlende_felder
    assert any("gebaut" in f for f in e.rueckfragen)
    assert e.rueckfragen[-1].startswith("Unter welcher Telefonnummer")
    assert "1. " in e.antwort


def test_neubau_fragt_nicht_nach_baujahr():
    e = analysiere(beispiel("05"))
    assert "baujahr" not in e.fehlende_felder
    assert not any("iSFP" in u for u in e.unterlagen)
    assert "Geplantes Gebäude" in e.antwort


def test_eilige_anfrage_hat_hohe_prioritaet():
    e = analysiere(beispiel("02"))
    assert e.prioritaet == "hoch"
    assert "kurzfristig" in e.antwort
    assert any("Zeitdruck" in h for h in e.hinweise)


def test_ki_ergebnis_wird_genutzt_und_ergaenzt():
    def fake_ki(einst, system, nutzer, schema):
        assert "Kundenanfrage" in nutzer and schema is not None
        return json.dumps({"leistungen": ["isfp"], "baujahr": 1965, "heizung": "Ölheizung", "name": None})

    e = analysiere(beispiel("01"), ki=OLLAMA, ki_funktion=fake_ki)
    assert e.anfrage.baujahr == 1965  # Wert der KI
    assert e.anfrage.heizung == "Öl"
    assert e.anfrage.name == "Sabine Krüger"  # Lücke von den Regeln gefüllt
    assert e.anfrage.leistungen == ["isfp"]
    assert e.quelle.startswith("KI: Ollama")
    assert e.warnungen == []


def test_ki_ausfall_faellt_auf_regeln_zurueck():
    def kaputte_ki(*_):
        raise KIFehler("Ollama ist nicht erreichbar.")

    e = analysiere(beispiel("01"), ki=OLLAMA, ki_funktion=kaputte_ki)
    assert e.quelle == "Regeln (ohne KI)"
    assert e.anfrage.baujahr == 1972
    assert "nicht erreichbar" in e.warnungen[0]


def test_glaetten_darf_keine_inhalte_verlieren():
    def ki(einst, system, nutzer, schema):
        if schema is not None:
            return "{}"
        return "Hallo! Kurz und knapp: Das kostet 500 €."  # zu kurz und mit Preis → abgelehnt

    e = analysiere(beispiel("03"), ki=OLLAMA, glaetten=True, ki_funktion=ki)
    assert "500" not in e.antwort
    assert any("Originalentwurf" in w for w in e.warnungen)


def test_glaetten_ok():
    def ki(einst, system, nutzer, schema):
        if schema is not None:
            return "{}"
        return nutzer.replace("vielen Dank für Ihre Anfrage", "herzlichen Dank für Ihre Nachricht")

    e = analysiere(beispiel("03"), ki=OLLAMA, glaetten=True, ki_funktion=ki)
    assert "herzlichen Dank" in e.antwort
    assert e.warnungen == []


def test_eigene_signatur():
    e = analysiere(beispiel("06"), signatur="Max Muster\nIngenieurbüro Muster")
    assert e.antwort.endswith("Max Muster\nIngenieurbüro Muster")
