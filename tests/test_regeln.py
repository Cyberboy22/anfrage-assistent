"""Die Regeln müssen alle Beispiel-Anfragen ohne KI richtig lesen."""

from conftest import beispiel

from assistent.regeln import analysiere_mit_regeln, erkenne_heizung, erkenne_leistungen, erkenne_wohnflaeche


def test_isfp_und_foerderung():
    a = analysiere_mit_regeln(beispiel("01"))
    assert a.leistungen == ["isfp", "foerdermittel"]
    assert a.name == "Sabine Krüger"
    assert a.email == "sabine.krueger@example.com"
    assert a.telefon == "0221 4710 123"
    assert (a.gebaeudetyp, a.baujahr, a.wohnflaeche_m2) == ("Einfamilienhaus", 1972, 145.0)
    assert a.heizung == "Gas"  # die Wärmepumpe ist nur geplant
    assert (a.plz, a.ort) == ("50733", "Köln-Nippes")
    assert a.massnahmen == ["Dach", "Fenster", "Heizung"]
    assert a.zeitplan == "im Frühjahr 2027"
    assert a.auftraege_vergeben is False


def test_energieausweis_mit_frist():
    a = analysiere_mit_regeln(beispiel("02"))
    assert a.leistungen == ["energieausweis"]
    assert a.gebaeudetyp == "Mehrfamilienhaus"
    assert a.wohneinheiten == 6
    assert a.baujahr == 1961
    assert a.heizung == "Öl"
    assert a.anlass_ausweis == "Verkauf"
    assert "Notartermin" in a.frist  # Satz aus dem Text, nicht der Betreff
    assert a.wohnflaeche_m2 is None


def test_heizlast_unterscheidet_alte_und_neue_heizung():
    a = analysiere_mit_regeln(beispiel("03"))
    assert a.leistungen == ["heizlast"]
    assert a.gebaeudetyp == "Reihenhaus"
    assert a.heizung == "Öl"
    assert "Heizung" in a.massnahmen
    assert "Fenster" not in a.massnahmen  # wurden 2012 schon getauscht
    assert a.baujahr is None


def test_energieaudit_gewerbe():
    a = analysiere_mit_regeln(beispiel("04"))
    assert a.leistungen == ["energieaudit"]  # "BAFA-zertifiziert" ist keine Förderanfrage
    assert a.unternehmen == "Rheinland Logistik GmbH"
    assert a.name == "Dr. Miriam Hoffmann"
    assert a.wohnflaeche_m2 == 4500.0
    assert a.gebaeudetyp == "Nichtwohngebäude"


def test_neubau():
    a = analysiere_mit_regeln(beispiel("05"))
    assert set(a.leistungen) == {"neubau", "foerdermittel"}
    assert a.name == "Lena und Marco Schulz"
    assert a.ort == "Pulheim"


def test_unklare_anfrage():
    a = analysiere_mit_regeln(beispiel("06"))
    assert a.leistungen == ["beratung"]
    assert a.name == "Peter"
    assert a.email is None


def test_vorhandener_ausweis_ist_keine_anfrage():
    text = "Wir haben bereits einen Energieausweis von 2015. Jetzt möchten wir einen Sanierungsfahrplan."
    assert erkenne_leistungen(text) == ["isfp"]


def test_grundstueck_ist_keine_wohnflaeche():
    assert erkenne_wohnflaeche("Grundstück 600 m², das Haus hat 120 m².") == 120.0
    assert erkenne_wohnflaeche("Wohnfläche: 1.250 qm") == 1250.0


def test_heizung_aktuell_vs_geplant():
    assert erkenne_heizung("Wir heizen derzeit mit Fernwärme.") == ("Fernwärme", False)
    assert erkenne_heizung("Wir möchten eine Wärmepumpe einbauen.") == (None, True)


def test_freie_kurze_anfrage():
    a = analysiere_mit_regeln("Hi, DHH Bj. 1958, 110qm, Nachtspeicher. Brauchen einen Energieausweis weil neue Mieter einziehen. LG Anna Roth, 0221 4710 999")
    assert (a.gebaeudetyp, a.baujahr, a.wohnflaeche_m2) == ("Doppelhaushälfte", 1958, 110.0)
    assert a.heizung == "Nachtspeicher/Strom"
    assert a.anlass_ausweis == "Vermietung"
    assert a.name == "Anna Roth"


def test_fachplanung_ist_keine_geplante_heizung():
    a = analysiere_mit_regeln(
        "Für unser Bürogebäude in 50667 Köln (Baujahr 1994, 2.300 m² Nutzfläche, Fernwärme) suchen wir eine "
        "Fachplanung und Baubegleitung für die Fassadendämmung und neue Fenster. Start ist für Herbst 2027 geplant."
    )
    assert a.heizung == "Fernwärme"
    assert a.massnahmen == ["Fassade", "Fenster"]
    assert a.zeitplan == "Herbst 2027"
    assert a.leistungen == ["baubegleitung"]
