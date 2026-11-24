"""Erkennung ohne KI: reguläre Ausdrücke und Schlüsselwörter.

Funktioniert sofort und ohne Installation eines Sprachmodells. Dient außerdem
als Sicherheitsnetz: Was die KI nicht findet, wird hier ergänzt.
"""

from __future__ import annotations

import datetime as _dt
import re

from .schema import Anfrage

_I = re.IGNORECASE

# --- Leistungen ---------------------------------------------------------------

LEISTUNG_MUSTER: dict[str, tuple[str, ...]] = {
    "isfp": (r"sanierungsfahrplan", r"\bisfp\b", r"sanierungs-?fahrplan"),
    "energieausweis": (r"energieausweis", r"energiepass", r"bedarfsausweis", r"verbrauchsausweis"),
    "foerdermittel": (r"förder", r"foerder", r"\bbafa\b(?!-?\s*(?:zertifiziert|gelistet|zugelassen))", r"\bkfw\b", r"zuschuss", r"zuschüsse", r"\bbeg\b"),
    "heizlast": (r"heizlast",),
    "baubegleitung": (r"baubegleitung", r"fachplanung", r"bauüberwachung", r"baubegleit"),
    "energieaudit": (r"energieaudit", r"\baudit\b", r"16247", r"\bedl-?g\b"),
    "neubau": (r"neubau", r"\bqng\b", r"ökobilanz", r"\blca\b"),
}
# Wird eine Leistung nur als schon vorhanden erwähnt ("wir haben bereits einen
# Energieausweis"), ist sie keine neue Anfrage.
_SCHON_VORHANDEN = re.compile(r"(bereits|schon|alte[nrs]?|vorhandene[nrs]?|vorliegende[nrs]?)\s+(\w+\s+){0,2}$", _I)


def erkenne_leistungen(text: str) -> list[str]:
    gefunden: list[str] = []
    for key, muster in LEISTUNG_MUSTER.items():
        for m in muster:
            for treffer in re.finditer(m, text, _I):
                davor = text[max(0, treffer.start() - 40) : treffer.start()]
                if key in ("energieausweis", "isfp") and _SCHON_VORHANDEN.search(davor):
                    continue
                if key not in gefunden:
                    gefunden.append(key)
                break
            if key in gefunden:
                break
    return gefunden or ["beratung"]


# --- Gebäude ------------------------------------------------------------------

_GEBAEUDE_MUSTER = (
    ("Doppelhaushälfte", r"doppelhaush[äa]lfte|\bdhh\b"),
    ("Reihenhaus", r"reihen(?:mittel|end|eck)?haus|\brmh\b|\breh\b"),
    ("Mehrfamilienhaus", r"mehrfamilienhaus|\bmfh\b|mietshaus|mehrparteienhaus|wohnanlage"),
    ("Zweifamilienhaus", r"zweifamilienhaus|\bzfh\b"),
    ("Einfamilienhaus", r"einfamilienhaus|\befh\b"),
    (
        "Nichtwohngebäude",
        r"bürogebäude|verwaltungsgebäude|gewerbe(?:immobilie|halle|gebäude|objekt)|lagerhalle|"
        r"logistikhalle|produktionshalle|produktionsgebäude|nichtwohngebäude|\bhalle\b",
    ),
)

_BAUJAHR_MUSTER = (
    r"(?:baujahr|bj\.?)\s*[:\-]?\s*(?:ca\.?\s*|etwa\s*|um\s*)?((?:18|19|20)\d{2})",
    r"(?:gebaut|errichtet|erbaut|fertiggestellt)\s+(?:\w+\s+){0,3}?((?:18|19|20)\d{2})",
    r"((?:18|19|20)\d{2})\s+(?:gebaut|errichtet|erbaut|fertiggestellt)",
    r"(?:haus|gebäude|objekt|immobilie)\s+(?:\w+\s+){0,2}?(?:aus\s+(?:dem\s+jahr\s+)?|von\s+)((?:18|19|20)\d{2})\b",
)

_FLAECHE = r"(\d{1,3}(?:\.\d{3})+|\d{2,6}(?:[.,]\d{1,2})?)\s*(?:m²|m2|qm|quadratmeter)"

_ZAHLWOERTER = {
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7,
    "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
}  # fmt: skip

_HEIZ_MUSTER = (
    ("Fernwärme", r"fernwärme"),
    ("Wärmepumpe", r"wärmepumpe"),
    ("Nachtspeicher/Strom", r"nachtspeicher|elektroheizung|stromheizung"),
    ("Pellets/Holz", r"pellet|holzheizung|scheitholz|hackschnitzel"),
    ("Gas", r"gasheizung|gastherme|gas-?brennwert|gaskessel|erdgas|gas-?etagenheizung|\bgas\b"),
    ("Öl", r"ölheizung|öl-?brennwert|ölkessel|heizöl|\böl\b"),
)
_PLAN = re.compile(
    r"\bplan|geplant|möcht|woll|würd|überleg|ein(?:zu)?bau|um(?:zu)?steig|umstieg|ersetz|aus(?:zu)?tausch|"
    r"\btausch|install|anschaff|(?:zu\s+)?wechseln|zukünftig|künftig|später|\bneue[nr]?\b|\bsoll|"
    r"für\s+(?:die\s+|eine\s+|unsere\s+)?(?:neue\s+)?wärmepumpe",
    _I,
)
_VERGANGEN = re.compile(r"\b(?:wurden|wurde|worden|bereits|schon)\b", _I)
_AKTUELL = re.compile(
    r"aktuell|derzeit|momentan|zurzeit|bisher|noch\s+(eine|einen|mit)|heizen\s+mit|beheizt|vorhanden|"
    r"\balte[nr]?\b|bestehende|hat\s+eine|haben\s+eine|läuft",
    _I,
)

_MASSNAHMEN_MUSTER = (
    ("Dach", r"\bdach(?:es|s|dämmung|sanierung|fläche|flächen)?\b|aufsparren|zwischensparren"),
    ("Fassade", r"fassade|außenwand|außenwände|wärmedämmverbund|\bwdvs\b|außendämmung"),
    ("Fenster", r"fenster"),
    ("Kellerdecke", r"kellerdecke|kellerdämmung"),
    ("Oberste Geschossdecke", r"oberste\s+geschossdecke|dachboden\s+dämm"),
    (
        "Heizung",
        r"heizungstausch|neue\s+heizung|heizung\s+(?:erneuern|tauschen|austauschen|ersetzen|modernisieren)|"
        r"hydraulische[nr]?\s+abgleich|heizungsoptimierung",
    ),
    ("Photovoltaik", r"photovoltaik|\bpv\b|pv-anlage|solaranlage|solarthermie"),
    ("Lüftung", r"lüftungsanlage|wohnraumlüftung|lüftungskonzept|\blüftung\b"),
)

_STAEDTE = (
    "Köln", "Hürth", "Frechen", "Pulheim", "Brühl", "Bergheim", "Kerpen", "Wesseling",
    "Leverkusen", "Bonn", "Bergisch Gladbach", "Rösrath", "Troisdorf", "Dormagen",
    "Düsseldorf", "Aachen", "Erftstadt", "Bornheim", "Euskirchen", "Elsdorf",
)  # fmt: skip

_DRINGEND = re.compile(
    r"dringend|eilig|\beilt\b|asap|so schnell wie möglich|schnellstmöglich|zeitnah|kurzfristig|"
    r"notartermin|\bfrist\b|deadline|bis spätestens|bis zum \d{1,2}\.|in (?:zwei|drei|vier|\d) wochen|"
    r"nächste[nr]? woche",
    _I,
)

_MONATE = r"januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember"
_ZEITPLAN = re.compile(
    rf"\b(?:(?:im|ab|bis|ende|anfang|mitte|spätestens)\s+)?(?:(?:des\s+)?(?:nächsten|kommenden)\s+)?"
    rf"(?:jahr(?:es)?|frühjahr|sommer|herbst|winter|{_MONATE})(?:\s+20\d{{2}})?"
    rf"|\b(?:nächstes|kommendes)\s+jahr|\b(?:in\s+)?20[2-4]\d\b",
    _I,
)


def _ohne_betreff(text: str) -> str:
    """Die Betreffzeile ist oft ein Schlagwort ("… für Wärmepumpe") und kein ganzer Satz."""
    return "\n".join(z for z in text.splitlines() if not re.match(r"\s*betreff\s*:", z, _I))


def _saetze(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _teilsaetze(satz: str) -> list[str]:
    return [t for t in re.split(r",|;|\bund\b|\baber\b|\bsowie\b|\bdoch\b", satz, flags=_I) if t.strip()]


def _zahl_de(roh: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", roh):
        return float(roh.replace(".", ""))
    return float(roh.replace(",", "."))


def erkenne_baujahr(text: str) -> int | None:
    jahr_max = _dt.date.today().year + 5
    for muster in _BAUJAHR_MUSTER:
        m = re.search(muster, text, _I)
        if m:
            jahr = int(m.group(1))
            if 1800 <= jahr <= jahr_max:
                return jahr
    return None


def erkenne_wohnflaeche(text: str) -> float | None:
    # 1. Fläche direkt bei "Wohnfläche"/"Nutzfläche"
    m = re.search(r"(?:wohn|nutz)fläche\D{0,25}?" + _FLAECHE, text, _I)
    if not m:
        m = re.search(_FLAECHE + r"\s*(?:beheizte\s+)?(?:wohn|nutz)fläche", text, _I)
    if m:
        return _zahl_de(m.group(1))
    # 2. Sonst die erste Flächenangabe, die nicht zum Grundstück gehört
    for m in re.finditer(_FLAECHE, text, _I):
        davor = text[max(0, m.start() - 30) : m.start()].lower()
        if "grundstück" in davor or "garten" in davor:
            continue
        return _zahl_de(m.group(1))
    return None


def erkenne_wohneinheiten(text: str) -> int | None:
    m = re.search(
        r"\b(\d{1,3}|" + "|".join(_ZAHLWOERTER) + r")\s+(?:wohneinheiten|wohnungen|mietwohnungen|parteien|\bwe\b)",
        text,
        _I,
    )
    if not m:
        return None
    wert = m.group(1).lower()
    return int(wert) if wert.isdigit() else _ZAHLWOERTER[wert]


def erkenne_gebaeudetyp(text: str) -> str | None:
    for typ, muster in _GEBAEUDE_MUSTER:
        if re.search(muster, text, _I):
            return typ
    return None


def erkenne_heizung(text: str) -> tuple[str | None, bool]:
    """Gibt (aktuelle Heizung, neue Heizung geplant?) zurück."""
    aktuell: str | None = None
    geplant = False
    for satz in _saetze(_ohne_betreff(text)):
        for teil in _teilsaetze(satz):
            for typ, muster in _HEIZ_MUSTER:
                if not re.search(muster, teil, _I):
                    continue
                ist_plan = bool(_PLAN.search(teil)) and not _AKTUELL.search(teil)
                if ist_plan:
                    geplant = True
                elif aktuell is None:
                    aktuell = typ
                break
    return aktuell, geplant


def erkenne_massnahmen(text: str, heizung_geplant: bool) -> list[str]:
    gefunden: list[str] = []
    for satz in _saetze(_ohne_betreff(text)):
        if _VERGANGEN.search(satz) and not _PLAN.search(satz):
            continue  # "Die Fenster wurden 2012 schon getauscht" ist keine geplante Maßnahme
        for name, muster in _MASSNAHMEN_MUSTER:
            if name not in gefunden and re.search(muster, satz, _I):
                gefunden.append(name)
    if heizung_geplant and "Heizung" not in gefunden:
        gefunden.append("Heizung")
    return gefunden


def erkenne_ort(text: str) -> tuple[str | None, str | None]:
    m = re.search(r"\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+(?:[\- ][A-ZÄÖÜ][a-zäöüß]+)?)", text)
    if m:
        return m.group(1), m.group(2)
    staedte = "|".join(re.escape(s) for s in _STAEDTE)
    m = re.search(rf"\b({staedte})(?:-([A-ZÄÖÜ][a-zäöüß]+))?\b", text)
    if m:
        return None, m.group(0)
    return None, None


def erkenne_email(text: str) -> str | None:
    m = re.search(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", text)
    return m.group(0) if m else None


def erkenne_telefon(text: str) -> str | None:
    for m in re.finditer(r"(?<![\w.])((?:\+49|0049|0)\s?[1-9][\d\s/()\-]{5,}\d)", text):
        nummer = m.group(1).strip()
        ziffern = re.sub(r"\D", "", nummer)
        if 8 <= len(ziffern) <= 15:
            return re.sub(r"\s+", " ", nummer)
    return None


_GRUSS = re.compile(
    r"^\s*(?:mit\s+)?(?:freundlichen|besten|herzlichen|lieben|viele|beste|schöne|liebe)?\s*"
    r"(?:grüße?n?|gruß)\b[,!.]?\s*(.*)$|^\s*(?:vg|lg|mfg)\b[,!.]?\s*(.*)$",
    _I,
)
_NAME = re.compile(
    r"^(?:(?:Dr|Prof)\.\s+)?[A-ZÄÖÜ][a-zäöüß\-]+(?:\s+(?:und|&)\s+[A-ZÄÖÜ][a-zäöüß\-]+)?"
    r"(?:\s+(?:von\s+|van\s+|de\s+)?[A-ZÄÖÜ][a-zäöüß\-]+){0,3}$"
)


def erkenne_name(text: str) -> str | None:
    m = re.search(r"^von:\s*\"?([^<\"\n]+?)\"?\s*<", text, _I | re.M)
    if m and _NAME.match(m.group(1).strip()):
        return m.group(1).strip()
    zeilen = text.splitlines()
    for i in range(len(zeilen) - 1, -1, -1):
        g = _GRUSS.match(zeilen[i])
        if not g:
            continue
        rest = (g.group(1) or g.group(2) or "").split(",")[0].strip(" ,")
        if rest and _NAME.match(rest):
            return rest
        for folgezeile in zeilen[i + 1 : i + 4]:
            kandidat = folgezeile.strip()
            if not kandidat:
                continue
            if _NAME.match(kandidat):
                return kandidat
            break
    # Gruß mitten in einer Zeile: "… einziehen. LG Anna Roth, 0221 …"
    m = re.search(
        r"(?i:\b(?:lg|vg|mfg|gruß|grüße|grüßen))[,!.]?\s+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,2})",
        text,
    )
    if m:
        return m.group(1)
    m = re.search(r"(?:mein name ist|ich bin|hier schreibt)\s+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+){0,2})", text)
    return m.group(1) if m else None


def erkenne_unternehmen(text: str) -> str | None:
    m = re.search(
        r"\b((?:[A-ZÄÖÜ][\w&\-]*\s+){0,4}?[A-ZÄÖÜ][\w&\-]*\s+(?:GmbH(?:\s*&\s*Co\.\s*KG)?|AG|KG|OHG|UG(?:\s*\(haftungsbeschränkt\))?|e\.\s?V\.|GbR|mbH))",
        text,
    )
    return m.group(1).strip() if m else None


def erkenne_zeitplan(text: str) -> str | None:
    jahr = _dt.date.today().year
    for satz in _saetze(_ohne_betreff(text)):
        if not re.search(
            r"\bplan|geplant|möcht|woll|würd|gern|lassen|beginn|start|umsetz|angehen|sanier|um(?:zu)?steig|soll|"
            r"bauantrag|bauen|dämmen|erneuern|tauschen|vorhaben",
            satz,
            _I,
        ):
            continue
        for m in _ZEITPLAN.finditer(satz):
            fund = m.group(0).strip()
            j = re.search(r"20\d{2}", fund)
            if j and int(j.group(0)) < jahr:
                continue  # Vergangenheit, z. B. Kaufjahr
            return fund
    return None


def erkenne_auftraege(text: str) -> bool | None:
    if re.search(r"(?:noch\s+)?(?:keine|nicht|nichts)\s+(?:\w+\s+){0,2}(?:aufträge|beauftragt|unterschrieben|vergeben)", text, _I):
        return False
    if re.search(r"(?:bereits|schon)\s+(?:\w+\s+){0,2}(?:beauftragt|unterschrieben|vergeben)|auftrag\s+(?:ist\s+)?(?:erteilt|vergeben)", text, _I):
        return True
    return None


def erkenne_anlass_ausweis(text: str) -> str | None:
    if re.search(r"verkauf|verkaufen|notar|käufer|kaufinteressent|makler", text, _I):
        return "Verkauf"
    if re.search(r"vermiet|neue[nr]? mieter|mieterwechsel", text, _I):
        return "Vermietung"
    return None


def erkenne_frist(text: str) -> str | None:
    # Zuerst im eigentlichen Text suchen, erst dann im Betreff
    for quelle in (_ohne_betreff(text), erkenne_betreff(text) or ""):
        for satz in _saetze(quelle):
            if _DRINGEND.search(satz):
                return satz if len(satz) <= 160 else satz[:157] + "…"
    return None


def erkenne_betreff(text: str) -> str | None:
    m = re.search(r"^\s*betreff\s*:\s*(.+)$", text, _I | re.M)
    return m.group(1).strip() if m else None


def analysiere_mit_regeln(text: str) -> Anfrage:
    heizung, heizung_geplant = erkenne_heizung(text)
    plz, ort = erkenne_ort(text)
    leistungen = erkenne_leistungen(text)
    unternehmen = erkenne_unternehmen(text)
    gebaeudetyp = erkenne_gebaeudetyp(text)
    wohneinheiten = erkenne_wohneinheiten(text)
    anlass = erkenne_anlass_ausweis(text) if "energieausweis" in leistungen else None

    return Anfrage.from_dict(
        {
            "name": erkenne_name(text),
            "email": erkenne_email(text),
            "telefon": erkenne_telefon(text),
            "unternehmen": unternehmen,
            "leistungen": leistungen,
            "gebaeudetyp": gebaeudetyp,
            "baujahr": erkenne_baujahr(text),
            "wohnflaeche_m2": erkenne_wohnflaeche(text),
            "wohneinheiten": wohneinheiten,
            "heizung": heizung,
            "plz": plz,
            "ort": ort,
            "massnahmen": erkenne_massnahmen(text, heizung_geplant),
            "zeitplan": erkenne_zeitplan(text),
            "auftraege_vergeben": erkenne_auftraege(text),
            "anlass_ausweis": anlass,
            "frist": erkenne_frist(text),
            "betreff": erkenne_betreff(text),
        }
    )
