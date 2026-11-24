"""Rückfragen, Unterlagen-Checkliste und Antwortentwurf.

Der Antwortentwurf entsteht aus einer festen Vorlage. Er enthält nur Angaben,
die wirklich in der Anfrage standen – keine erfundenen Preise, Fristen oder
Zusagen. Die KI darf den Text optional sprachlich glätten (siehe pipeline.py).
"""

from __future__ import annotations

from .leistungen import FELD_REIHENFOLGE, FRAGEN, LEISTUNGEN
from .schema import Anfrage


_NICHT_BEI_NEUBAU = {"baujahr", "heizung", "massnahmen", "auftraege_vergeben"}


def benoetigte_felder(anfrage: Anfrage) -> list[str]:
    felder: list[str] = []
    for key in anfrage.leistungen or ["beratung"]:
        for feld in LEISTUNGEN[key].pflichtfelder:
            if feld not in felder:
                felder.append(feld)
    if anfrage.gebaeudetyp == "Mehrfamilienhaus" and "wohneinheiten" not in felder:
        felder.append("wohneinheiten")
    if "neubau" in anfrage.leistungen:
        # Bei einem Neubau gibt es kein Baujahr, keine bestehende Heizung und keine Sanierungsmaßnahmen
        felder = [f for f in felder if f not in _NICHT_BEI_NEUBAU]
    felder.append("telefon")
    return felder


def fehlende_felder(anfrage: Anfrage) -> list[str]:
    benoetigt = benoetigte_felder(anfrage)
    fehlend = [f for f in benoetigt if anfrage.ist_leer(f)]
    return sorted(fehlend, key=lambda f: FELD_REIHENFOLGE.index(f) if f in FELD_REIHENFOLGE else 99)


def rueckfragen(anfrage: Anfrage) -> list[str]:
    fragen: list[str] = []
    for feld in fehlende_felder(anfrage):
        frage = FRAGEN.get(feld)
        if feld == "wohnflaeche_m2" and anfrage.gebaeudetyp == "Nichtwohngebäude":
            frage = "Wie groß ist die beheizte Nutzfläche ungefähr (in m²)?"
        if frage and frage not in fragen:
            fragen.append(frage)
    for key in anfrage.leistungen or ["beratung"]:
        for frage in LEISTUNGEN[key].zusatzfragen:
            if frage not in fragen:
                fragen.append(frage)
    # Telefon-Rückfrage immer zuletzt
    tel = FRAGEN["telefon"]
    if tel in fragen:
        fragen.remove(tel)
        fragen.append(tel)
    return fragen


def unterlagen(anfrage: Anfrage) -> list[str]:
    liste: list[str] = []
    for key in anfrage.leistungen or ["beratung"]:
        for u in LEISTUNGEN[key].unterlagen:
            if "neubau" in anfrage.leistungen and "iSFP" in u:
                continue
            if u not in liste:
                liste.append(u)
    return liste


def interne_hinweise(anfrage: Anfrage) -> list[str]:
    """Hinweise nur für das Büro – erscheinen nicht in der Antwort an den Kunden."""
    hinweise: list[str] = []
    if anfrage.frist:
        hinweise.append(f"Zeitdruck erwähnt: „{anfrage.frist}“ – zeitnah zurückmelden.")
    if "foerdermittel" in anfrage.leistungen and anfrage.auftraege_vergeben:
        hinweise.append("Kunde hat laut Anfrage schon Aufträge vergeben – Förderfähigkeit (Antrag vor Vorhabenbeginn) prüfen.")
    if anfrage.kundentyp == "gewerblich":
        hinweise.append("Gewerbekunde – ggf. andere Förderprogramme (Nichtwohngebäude/Wirtschaft) prüfen.")
    passende = {"beratung", "foerdermittel", "heizlast", "baubegleitung"}
    if anfrage.baujahr and anfrage.baujahr < 1978 and "isfp" not in anfrage.leistungen and passende & set(anfrage.leistungen):
        hinweise.append("Gebäude vor 1978 – vermutlich großes Einsparpotenzial, einen iSFP als nächsten Schritt anbieten.")
    if not anfrage.email:
        hinweise.append("Keine E-Mail-Adresse erkannt – Antwortadresse prüfen.")
    return hinweise


def prioritaet(anfrage: Anfrage) -> str:
    return "hoch" if anfrage.frist else "normal"


def _flaeche(m2: float) -> str:
    if float(m2).is_integer():
        return f"{int(m2):,}".replace(",", ".")
    return f"{m2:.1f}".replace(".", ",")


def notierte_angaben(anfrage: Anfrage) -> list[str]:
    zeilen: list[str] = []
    gebaeude = []
    if anfrage.gebaeudetyp:
        gebaeude.append(anfrage.gebaeudetyp)
    if anfrage.baujahr:
        gebaeude.append(f"Baujahr {anfrage.baujahr}")
    if anfrage.wohnflaeche_m2:
        art = "Nutzfläche" if anfrage.gebaeudetyp == "Nichtwohngebäude" else "Wohnfläche"
        gebaeude.append(f"ca. {_flaeche(anfrage.wohnflaeche_m2)} m² {art}")
    if anfrage.wohneinheiten:
        gebaeude.append(f"{anfrage.wohneinheiten} Wohneinheiten")
    if gebaeude:
        titel = "Geplantes Gebäude" if "neubau" in anfrage.leistungen else "Gebäude"
        zeilen.append(f"{titel}: " + ", ".join(gebaeude))
    if anfrage.heizung:
        zeilen.append(f"Heizung aktuell: {anfrage.heizung}")
    standort = " ".join(x for x in (anfrage.plz, anfrage.ort) if x)
    if standort:
        zeilen.append(f"Standort: {standort}")
    if anfrage.massnahmen:
        zeilen.append("Geplante Maßnahmen: " + ", ".join(anfrage.massnahmen))
    if anfrage.zeitplan:
        zeilen.append(f"Zeitplan: {anfrage.zeitplan}")
    if anfrage.anlass_ausweis and "energieausweis" in anfrage.leistungen:
        zeilen.append(f"Anlass: {anfrage.anlass_ausweis}")
    return zeilen


def _aufzaehlung(teile: list[str]) -> str:
    if len(teile) <= 1:
        return "".join(teile)
    return ", ".join(teile[:-1]) + " und " + teile[-1]


def betreff(anfrage: Anfrage) -> str:
    if anfrage.betreff:
        return anfrage.betreff if anfrage.betreff.lower().startswith(("re:", "aw:")) else f"AW: {anfrage.betreff}"
    namen = [LEISTUNGEN[k].name for k in anfrage.leistungen or ["beratung"]]
    return "Ihre Anfrage: " + _aufzaehlung(namen)


def antwortentwurf(anfrage: Anfrage, signatur: str = "Ihr Team der Energieberatung") -> str:
    leistungen = anfrage.leistungen or ["beratung"]
    anrede = f"Guten Tag {anfrage.name}," if anfrage.name else "Guten Tag,"
    teile = [anrede, ""]

    if leistungen == ["beratung"]:
        teile.append("vielen Dank für Ihre Anfrage und Ihr Interesse an einer Energieberatung.")
    else:
        saetze = _aufzaehlung([LEISTUNGEN[k].im_satz for k in leistungen])
        teile.append(f"vielen Dank für Ihre Anfrage. Gern unterstützen wir Sie bei Ihrem Vorhaben und erstellen Ihnen {saetze}.")

    angaben = notierte_angaben(anfrage)
    if angaben:
        teile += ["", "Folgende Angaben haben wir bereits notiert:"]
        teile += [f"- {z}" for z in angaben]

    fragen = rueckfragen(anfrage)
    if fragen:
        teile += ["", "Damit wir Ihnen ein passendes Angebot erstellen können, benötigen wir noch einige Informationen:"]
        teile += [f"{i}. {f}" for i, f in enumerate(fragen, start=1)]

    docs = unterlagen(anfrage)
    if docs:
        teile += ["", "Falls vorhanden, senden Sie uns bitte außerdem folgende Unterlagen (gern als Foto oder Scan):"]
        teile += [f"- {u}" for u in docs]

    teile.append("")
    if anfrage.frist:
        teile.append("Sie haben erwähnt, dass es zeitlich eilt. Wir melden uns deshalb kurzfristig bei Ihnen, um das weitere Vorgehen abzustimmen.")
    else:
        teile.append("Sobald uns die Angaben vorliegen, melden wir uns mit einem Angebot und einem Terminvorschlag für eine Vor-Ort-Begehung.")
    teile += ["", "Bei Fragen erreichen Sie uns jederzeit gern telefonisch oder per E-Mail.", "", "Mit freundlichen Grüßen", signatur.strip()]
    return "\n".join(teile)
