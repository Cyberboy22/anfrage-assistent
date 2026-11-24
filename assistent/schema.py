"""Datenmodell einer Kundenanfrage und Normalisierung von (KI-)Ausgaben.

Egal ob die Daten aus den Regeln oder aus einem Sprachmodell kommen: Alles läuft
durch ``Anfrage.from_dict``. Dort werden Werte auf feste Kategorien abgebildet,
Zahlen geprüft und alles Unplausible verworfen. So kann ein Sprachmodell keine
Fantasiewerte in die Antwort schmuggeln.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import asdict, dataclass, field

GEBAEUDETYPEN = (
    "Einfamilienhaus",
    "Zweifamilienhaus",
    "Mehrfamilienhaus",
    "Reihenhaus",
    "Doppelhaushälfte",
    "Nichtwohngebäude",
)
HEIZUNGEN = (
    "Gas",
    "Öl",
    "Fernwärme",
    "Wärmepumpe",
    "Pellets/Holz",
    "Nachtspeicher/Strom",
    "Sonstige",
)
MASSNAHMEN = (
    "Dach",
    "Fassade",
    "Fenster",
    "Kellerdecke",
    "Oberste Geschossdecke",
    "Heizung",
    "Photovoltaik",
    "Lüftung",
)
LEISTUNGS_KEYS = (
    "isfp",
    "energieausweis",
    "foerdermittel",
    "heizlast",
    "baubegleitung",
    "energieaudit",
    "neubau",
    "beratung",
)

# Synonyme: (Teilstring in Kleinbuchstaben, Zielwert). Reihenfolge ist wichtig,
# spezifischere Begriffe stehen vor allgemeineren.
_SYN_GEBAEUDE = (
    ("doppelhaus", "Doppelhaushälfte"),
    ("dhh", "Doppelhaushälfte"),
    ("reihen", "Reihenhaus"),
    ("mehrfamilien", "Mehrfamilienhaus"),
    ("mehrparteien", "Mehrfamilienhaus"),
    ("mfh", "Mehrfamilienhaus"),
    ("zweifamilien", "Zweifamilienhaus"),
    ("zfh", "Zweifamilienhaus"),
    ("einfamilien", "Einfamilienhaus"),
    ("efh", "Einfamilienhaus"),
    ("nichtwohn", "Nichtwohngebäude"),
    ("gewerb", "Nichtwohngebäude"),
    ("büro", "Nichtwohngebäude"),
    ("halle", "Nichtwohngebäude"),
    ("praxis", "Nichtwohngebäude"),
)
_SYN_HEIZUNG = (
    ("fernwärme", "Fernwärme"),
    ("fernwaerme", "Fernwärme"),
    ("wärmepumpe", "Wärmepumpe"),
    ("waermepumpe", "Wärmepumpe"),
    ("nachtspeicher", "Nachtspeicher/Strom"),
    ("elektro", "Nachtspeicher/Strom"),
    ("strom", "Nachtspeicher/Strom"),
    ("pellet", "Pellets/Holz"),
    ("holz", "Pellets/Holz"),
    ("gas", "Gas"),
    ("öl", "Öl"),
    ("oel", "Öl"),
)
_SYN_MASSNAHMEN = (
    ("geschossdecke", "Oberste Geschossdecke"),
    ("dachboden", "Oberste Geschossdecke"),
    ("dach", "Dach"),
    ("fassade", "Fassade"),
    ("außenwand", "Fassade"),
    ("aussenwand", "Fassade"),
    ("wdvs", "Fassade"),
    ("fenster", "Fenster"),
    ("keller", "Kellerdecke"),
    ("heiz", "Heizung"),
    ("wärmepumpe", "Heizung"),
    ("photovoltaik", "Photovoltaik"),
    ("pv", "Photovoltaik"),
    ("solar", "Photovoltaik"),
    ("lüftung", "Lüftung"),
    ("lueftung", "Lüftung"),
)
_SYN_LEISTUNG = (
    ("isfp", "isfp"),
    ("sanierungsfahrplan", "isfp"),
    ("energieausweis", "energieausweis"),
    ("förder", "foerdermittel"),
    ("foerder", "foerdermittel"),
    ("heizlast", "heizlast"),
    ("baubegleitung", "baubegleitung"),
    ("fachplanung", "baubegleitung"),
    ("audit", "energieaudit"),
    ("neubau", "neubau"),
    ("energiekonzept", "neubau"),
    ("beratung", "beratung"),
)
_SYN_KUNDENTYP = (
    ("gewerb", "gewerblich"),
    ("firma", "gewerblich"),
    ("unternehm", "gewerblich"),
    ("privat", "privat"),
)

_LEER = {
    "",
    "null",
    "none",
    "unbekannt",
    "unklar",
    "keine",
    "n/a",
    "na",
    "-",
    "keine angabe",
    "nicht angegeben",
}


def _text(wert) -> str | None:
    if wert is None or isinstance(wert, (list, dict, bool)):
        return None
    s = str(wert).strip()
    return None if s.lower() in _LEER else s


def _enum(wert, synonyme, optionen, sonst=None) -> str | None:
    s = _text(wert)
    if s is None:
        return None
    low = s.lower()
    for option in optionen:
        if low == option.lower():
            return option
    for teil, ziel in synonyme:
        if teil in low:
            return ziel
    return sonst


def _liste(wert, synonyme, optionen) -> list[str]:
    if wert is None:
        return []
    if isinstance(wert, str):
        wert = re.split(r"[,;]|\bund\b|\bsowie\b", wert)
    if not isinstance(wert, (list, tuple)):
        return []
    ergebnis: list[str] = []
    for eintrag in wert:
        norm = _enum(eintrag, synonyme, optionen)
        if norm and norm not in ergebnis:
            ergebnis.append(norm)
    return ergebnis


_ZAHL = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


def zahl_aus_text(wert) -> float | None:
    """'1.250 m²' -> 1250.0, '145,5' -> 145.5, 140 -> 140.0"""
    if isinstance(wert, bool) or wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    treffer = _ZAHL.search(str(wert))
    if not treffer:
        return None
    roh = treffer.group(0)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", roh):
        roh = roh.replace(".", "")
    return float(roh.replace(",", "."))


def _int_bereich(wert, minimum: int, maximum: int) -> int | None:
    z = zahl_aus_text(wert)
    if z is None:
        return None
    z = int(round(z))
    return z if minimum <= z <= maximum else None


def _bool(wert) -> bool | None:
    if isinstance(wert, bool):
        return wert
    s = _text(wert)
    if s is None:
        return None
    low = s.lower()
    if low.startswith(("nein", "false", "no", "noch nicht", "nicht")):
        return False
    if low.startswith(("ja", "true", "yes", "bereits", "schon")):
        return True
    return None


@dataclass
class Anfrage:
    """Alle Angaben, die aus einer Kundenanfrage erkannt werden."""

    name: str | None = None
    email: str | None = None
    telefon: str | None = None
    kundentyp: str | None = None  # "privat" | "gewerblich"
    unternehmen: str | None = None
    leistungen: list[str] = field(default_factory=list)
    gebaeudetyp: str | None = None
    baujahr: int | None = None
    wohnflaeche_m2: float | None = None
    wohneinheiten: int | None = None
    heizung: str | None = None
    plz: str | None = None
    ort: str | None = None
    massnahmen: list[str] = field(default_factory=list)
    zeitplan: str | None = None
    auftraege_vergeben: bool | None = None
    anlass_ausweis: str | None = None
    frist: str | None = None
    betreff: str | None = None

    @classmethod
    def from_dict(cls, daten: dict | None) -> "Anfrage":
        """Baut eine Anfrage aus beliebigen (z. B. KI-)Daten und prüft jeden Wert."""
        d = daten if isinstance(daten, dict) else {}
        jahr = _dt.date.today().year

        email = _text(d.get("email"))
        if email and not re.fullmatch(r"[\w.+\-]+@[\w\-]+(\.[\w\-]+)+", email):
            email = None

        plz = _text(d.get("plz"))
        if plz:
            m = re.search(r"\b\d{5}\b", plz)
            plz = m.group(0) if m else None

        flaeche = zahl_aus_text(d.get("wohnflaeche_m2"))
        if flaeche is not None and not 10 <= flaeche <= 200_000:
            flaeche = None

        leistungen = _liste(d.get("leistungen"), _SYN_LEISTUNG, LEISTUNGS_KEYS)
        if len(leistungen) > 1 and "beratung" in leistungen:
            leistungen.remove("beratung")

        return cls(
            name=_text(d.get("name")),
            email=email,
            telefon=_text(d.get("telefon")),
            kundentyp=_enum(d.get("kundentyp"), _SYN_KUNDENTYP, ("privat", "gewerblich")),
            unternehmen=_text(d.get("unternehmen")),
            leistungen=leistungen,
            gebaeudetyp=_enum(d.get("gebaeudetyp"), _SYN_GEBAEUDE, GEBAEUDETYPEN),
            baujahr=_int_bereich(d.get("baujahr"), 1800, jahr + 5),
            wohnflaeche_m2=flaeche,
            wohneinheiten=_int_bereich(d.get("wohneinheiten"), 1, 2000),
            heizung=_enum(d.get("heizung"), _SYN_HEIZUNG, HEIZUNGEN, sonst="Sonstige"),
            plz=plz,
            ort=_text(d.get("ort")),
            massnahmen=_liste(d.get("massnahmen"), _SYN_MASSNAHMEN, MASSNAHMEN),
            zeitplan=_text(d.get("zeitplan")),
            auftraege_vergeben=_bool(d.get("auftraege_vergeben")),
            anlass_ausweis=_text(d.get("anlass_ausweis")),
            frist=_text(d.get("frist")),
            betreff=_text(d.get("betreff")),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def ist_leer(self, feld: str) -> bool:
        wert = getattr(self, feld)
        return wert is None or wert == [] or wert == ""


def ergaenze(primaer: Anfrage, sekundaer: Anfrage) -> Anfrage:
    """Primäre Werte (z. B. KI) haben Vorrang, Lücken füllt die sekundäre Quelle (Regeln)."""
    zusammen = Anfrage()
    for feld in Anfrage.__dataclass_fields__:
        a, b = getattr(primaer, feld), getattr(sekundaer, feld)
        if feld == "leistungen":
            nutzbar = [x for x in a if x != "beratung"]
            setattr(zusammen, feld, list(a) if nutzbar else (list(b) or list(a)))
        elif isinstance(a, list):
            setattr(zusammen, feld, list(a) if a else list(b))
        else:
            setattr(zusammen, feld, a if a is not None else b)
    return zusammen


# Feldbeschreibung für Sprachmodelle (wird im Prompt mitgeschickt).
KI_FELDER = {
    "name": "string|null – Name der anfragenden Person",
    "email": "string|null",
    "telefon": "string|null",
    "kundentyp": "'privat'|'gewerblich'|null",
    "unternehmen": "string|null – Firmenname, falls gewerblich",
    "leistungen": "Liste aus: " + ", ".join(LEISTUNGS_KEYS),
    "gebaeudetyp": "einer von: " + ", ".join(GEBAEUDETYPEN) + " | null",
    "baujahr": "Zahl|null",
    "wohnflaeche_m2": "Zahl|null – beheizte Wohn- bzw. Nutzfläche",
    "wohneinheiten": "Zahl|null",
    "heizung": "AKTUELLE Heizung, einer von: " + ", ".join(HEIZUNGEN) + " | null",
    "plz": "string|null",
    "ort": "string|null – Ort des Gebäudes (ggf. mit Stadtteil)",
    "massnahmen": "geplante Maßnahmen, Liste aus: " + ", ".join(MASSNAHMEN),
    "zeitplan": "string|null – wann die Maßnahmen geplant sind",
    "auftraege_vergeben": "true|false|null",
    "anlass_ausweis": "string|null – Anlass für den Energieausweis (z. B. Verkauf, Vermietung)",
    "frist": "string|null – Frist oder Eile, kurz zitiert",
}

KI_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "telefon": {"type": ["string", "null"]},
        "kundentyp": {"type": ["string", "null"]},
        "unternehmen": {"type": ["string", "null"]},
        "leistungen": {"type": "array", "items": {"type": "string", "enum": list(LEISTUNGS_KEYS)}},
        "gebaeudetyp": {"type": ["string", "null"]},
        "baujahr": {"type": ["integer", "null"]},
        "wohnflaeche_m2": {"type": ["number", "null"]},
        "wohneinheiten": {"type": ["integer", "null"]},
        "heizung": {"type": ["string", "null"]},
        "plz": {"type": ["string", "null"]},
        "ort": {"type": ["string", "null"]},
        "massnahmen": {"type": "array", "items": {"type": "string", "enum": list(MASSNAHMEN)}},
        "zeitplan": {"type": ["string", "null"]},
        "auftraege_vergeben": {"type": ["boolean", "null"]},
        "anlass_ausweis": {"type": ["string", "null"]},
        "frist": {"type": ["string", "null"]},
    },
    "required": list(KI_FELDER.keys()),
}
