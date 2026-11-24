"""Leistungskatalog: Welche Angaben und Unterlagen braucht das Büro pro Leistung?

Diese Datei ist bewusst einfach gehalten, damit das Büro sie selbst anpassen
kann (neue Leistung, andere Fragen, andere Unterlagen), ohne den Rest des
Programms zu verstehen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Leistung:
    key: str
    name: str  # kurze Anzeige, z. B. "iSFP"
    im_satz: str  # für den Antworttext: "einen individuellen Sanierungsfahrplan (iSFP)"
    pflichtfelder: tuple[str, ...]
    zusatzfragen: tuple[str, ...] = ()
    unterlagen: tuple[str, ...] = ()


LEISTUNGEN: dict[str, Leistung] = {
    "isfp": Leistung(
        key="isfp",
        name="Sanierungsfahrplan (iSFP)",
        im_satz="einen individuellen Sanierungsfahrplan (iSFP)",
        pflichtfelder=("gebaeudetyp", "baujahr", "wohnflaeche_m2", "heizung", "ort"),
        unterlagen=(
            "Grundrisse, Schnitte oder Baupläne",
            "Fotos der Fassaden und der Heizungsanlage (inkl. Typenschild)",
            "Heizkostenabrechnungen bzw. Verbrauchsdaten der letzten drei Jahre",
            "Unterlagen zu bereits durchgeführten Sanierungen",
        ),
    ),
    "energieausweis": Leistung(
        key="energieausweis",
        name="Energieausweis",
        im_satz="einen Energieausweis",
        pflichtfelder=("gebaeudetyp", "baujahr", "wohnflaeche_m2", "heizung", "ort", "anlass_ausweis"),
        zusatzfragen=("Wünschen Sie einen Verbrauchs- oder einen Bedarfsausweis, oder sollen wir Sie dazu beraten?",),
        unterlagen=(
            "Verbrauchsdaten der letzten drei Jahre (für einen Verbrauchsausweis)",
            "Grundrisse bzw. Baupläne (für einen Bedarfsausweis)",
            "Fotos der Heizungsanlage (inkl. Typenschild)",
            "vorhandener alter Energieausweis",
        ),
    ),
    "foerdermittel": Leistung(
        key="foerdermittel",
        name="Fördermittelberatung",
        im_satz="eine Fördermittelberatung",
        pflichtfelder=("gebaeudetyp", "baujahr", "ort", "massnahmen", "zeitplan", "auftraege_vergeben"),
        unterlagen=(
            "Angebote der Handwerksbetriebe (falls schon vorhanden)",
            "vorhandener Sanierungsfahrplan (iSFP), falls es einen gibt",
        ),
    ),
    "heizlast": Leistung(
        key="heizlast",
        name="Heizlastberechnung",
        im_satz="eine Heizlastberechnung",
        pflichtfelder=("gebaeudetyp", "baujahr", "wohnflaeche_m2", "ort"),
        zusatzfragen=("Welche Bauteile wurden bereits gedämmt oder erneuert (z. B. Fenster, Dach)?",),
        unterlagen=(
            "Grundrisse mit Raummaßen",
            "Fotos der Heizkörper bzw. Heizflächen",
        ),
    ),
    "baubegleitung": Leistung(
        key="baubegleitung",
        name="Fachplanung & Baubegleitung",
        im_satz="eine energetische Fachplanung und Baubegleitung",
        pflichtfelder=("gebaeudetyp", "ort", "massnahmen", "zeitplan"),
        unterlagen=(
            "Angebote bzw. Leistungsverzeichnisse der geplanten Maßnahmen",
            "Förderzusage (falls vorhanden)",
        ),
    ),
    "energieaudit": Leistung(
        key="energieaudit",
        name="Energieaudit (DIN EN 16247-1)",
        im_satz="ein Energieaudit nach DIN EN 16247-1",
        pflichtfelder=("unternehmen", "ort"),
        zusatzfragen=(
            "Wie viele Standorte und Mitarbeitende hat Ihr Unternehmen?",
            "Wie hoch ist Ihr jährlicher Energieverbrauch ungefähr (Strom, Wärme, Kraftstoffe)?",
        ),
        unterlagen=(
            "Energierechnungen (Strom, Gas/Wärme, Kraftstoffe) der letzten Jahre",
            "Liste der Standorte und der wesentlichen Anlagen (z. B. Heizung, Druckluft, Kälte)",
        ),
    ),
    "neubau": Leistung(
        key="neubau",
        name="Energiekonzept Neubau",
        im_satz="ein Energiekonzept für Ihren Neubau",
        pflichtfelder=("gebaeudetyp", "ort"),
        zusatzfragen=("In welcher Planungsphase ist das Bauvorhaben, und ist bereits ein Architekturbüro beteiligt?",),
        unterlagen=(
            "Entwurfspläne (Grundrisse, Schnitte, Ansichten)",
            "Baubeschreibung",
        ),
    ),
    "beratung": Leistung(
        key="beratung",
        name="Allgemeine Energieberatung",
        im_satz="eine Energieberatung",
        pflichtfelder=("gebaeudetyp", "baujahr", "ort"),
        zusatzfragen=(
            "Worum geht es Ihnen genau – z. B. um einen Sanierungsfahrplan, einen Energieausweis "
            "oder Fördermittel für geplante Maßnahmen?",
        ),
        unterlagen=(),
    ),
}

# Anzeigenamen der Felder (für die Übersicht in der App)
FELD_LABELS: dict[str, str] = {
    "name": "Name",
    "email": "E-Mail",
    "telefon": "Telefon",
    "kundentyp": "Kundentyp",
    "unternehmen": "Unternehmen",
    "gebaeudetyp": "Gebäudetyp",
    "baujahr": "Baujahr",
    "wohnflaeche_m2": "Wohnfläche",
    "wohneinheiten": "Wohneinheiten",
    "heizung": "Heizung (aktuell)",
    "ort": "Standort",
    "massnahmen": "Geplante Maßnahmen",
    "zeitplan": "Zeitplan",
    "auftraege_vergeben": "Aufträge schon vergeben?",
    "anlass_ausweis": "Anlass Energieausweis",
    "frist": "Frist / Eile",
}

# Rückfrage pro fehlendem Feld (in dieser Reihenfolge im Antwortentwurf)
FRAGEN: dict[str, str] = {
    "unternehmen": "Wie lautet der Name Ihres Unternehmens?",
    "gebaeudetyp": "Um welche Art von Gebäude handelt es sich (z. B. Einfamilienhaus, Mehrfamilienhaus, Gewerbe)?",
    "baujahr": "In welchem Jahr wurde das Gebäude ungefähr gebaut?",
    "wohnflaeche_m2": "Wie groß ist die beheizte Wohnfläche ungefähr (in m²)?",
    "wohneinheiten": "Wie viele Wohneinheiten hat das Gebäude?",
    "heizung": "Wie wird das Gebäude aktuell beheizt (z. B. Gas, Öl, Fernwärme), und wie alt ist die Heizung ungefähr?",
    "ort": "Wo befindet sich das Gebäude (Straße, PLZ und Ort)?",
    "anlass_ausweis": "Wofür benötigen Sie den Energieausweis (z. B. Verkauf, Vermietung)?",
    "massnahmen": "Welche Maßnahmen planen Sie (z. B. Dämmung, neue Fenster, Heizungstausch)?",
    "zeitplan": "Wann möchten Sie mit den Maßnahmen beginnen?",
    "auftraege_vergeben": "Haben Sie für die geplanten Maßnahmen bereits Aufträge vergeben oder Verträge unterschrieben?",
    "telefon": "Unter welcher Telefonnummer erreichen wir Sie für eine kurze Abstimmung?",
}

FELD_REIHENFOLGE = tuple(FRAGEN.keys())
