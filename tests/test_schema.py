"""KI-Ausgaben werden geprüft und normalisiert, bevor sie verwendet werden."""

import pytest

from assistent.llm import KIFehler, lies_json
from assistent.schema import Anfrage, ergaenze


def test_normalisiert_freie_werte():
    a = Anfrage.from_dict(
        {
            "gebaeudetyp": "freistehendes EFH",
            "heizung": "Gas-Brennwerttherme",
            "baujahr": "ca. 1985",
            "wohnflaeche_m2": "140,5 m²",
            "massnahmen": "Dachdämmung und neue Fenster",
            "leistungen": ["iSFP", "Fördermittelberatung"],
            "auftraege_vergeben": "nein",
            "email": "kein@mail",
        }
    )
    assert a.gebaeudetyp == "Einfamilienhaus"
    assert a.heizung == "Gas"
    assert a.baujahr == 1985
    assert a.wohnflaeche_m2 == 140.5
    assert a.massnahmen == ["Dach", "Fenster"]
    assert a.leistungen == ["isfp", "foerdermittel"]
    assert a.auftraege_vergeben is False
    assert a.email is None  # ungültige Adresse wird verworfen


def test_unplausible_werte_fliegen_raus():
    a = Anfrage.from_dict({"baujahr": 3020, "wohnflaeche_m2": 2, "wohneinheiten": 0, "plz": "abc", "name": "null"})
    assert a.baujahr is None
    assert a.wohnflaeche_m2 is None
    assert a.wohneinheiten is None
    assert a.plz is None
    assert a.name is None


def test_kaputte_ki_daten():
    assert Anfrage.from_dict(None) == Anfrage()
    assert Anfrage.from_dict({"leistungen": "unbekannt", "massnahmen": 5}).leistungen == []


def test_ki_hat_vorrang_regeln_fuellen_luecken():
    ki = Anfrage(baujahr=1980, leistungen=["isfp"])
    regeln = Anfrage(baujahr=1975, ort="Köln", leistungen=["isfp", "energieausweis"])
    z = ergaenze(ki, regeln)
    assert z.baujahr == 1980
    assert z.ort == "Köln"
    assert z.leistungen == ["isfp"]


@pytest.mark.parametrize(
    "roh",
    [
        '{"baujahr": 1972}',
        '```json\n{"baujahr": 1972}\n```',
        'Hier das Ergebnis:\n{"baujahr": 1972}\nViele Grüße',
    ],
)
def test_lies_json_robust(roh):
    assert lies_json(roh) == {"baujahr": 1972}


def test_lies_json_fehler():
    with pytest.raises(KIFehler):
        lies_json("Ich kann das leider nicht.")
