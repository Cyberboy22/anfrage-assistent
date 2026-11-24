"""Der eigentliche Ablauf: Text rein → Ergebnis raus.

1. Regeln erkennen, was sicher erkennbar ist (immer, ohne KI).
2. Optional: Ein Sprachmodell liest die Anfrage und liefert JSON.
3. KI-Werte haben Vorrang, Lücken füllen die Regeln. Fällt die KI aus,
   läuft alles mit den Regeln weiter.
4. Abgleich mit dem Leistungskatalog → fehlende Angaben, Rückfragen, Unterlagen.
5. Antwortentwurf aus der Vorlage; optional sprachlich von der KI geglättet.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable

from . import antwort as a
from .llm import KIEinstellungen, KIFehler, frage_ki, lies_json
from .regeln import analysiere_mit_regeln
from .schema import KI_FELDER, KI_JSON_SCHEMA, Anfrage, ergaenze

MAX_ZEICHEN = 8000

SYSTEM_EXTRAKTION = """Du bist Assistent in einem Ingenieurbüro für Energieberatung.
Du liest Kundenanfragen (E-Mails) und überträgst die Angaben in ein JSON-Objekt.

Regeln:
- Erfinde nichts. Fehlt eine Angabe oder ist sie unklar: null bzw. leere Liste.
- leistungen: isfp = individueller Sanierungsfahrplan, energieausweis, foerdermittel = Fördermittelberatung
  (BAFA/KfW/BEG), heizlast = Heizlastberechnung, baubegleitung = energetische Fachplanung/Baubegleitung,
  energieaudit = Energieaudit für Unternehmen, neubau = Energiekonzept/QNG für einen Neubau,
  beratung = nur wenn sonst nichts passt.
- Eine Leistung, die der Kunde schon HAT (z. B. "wir haben bereits einen Energieausweis"), ist keine neue Anfrage.
- heizung ist die AKTUELLE Heizung. Eine nur geplante neue Heizung gehört als "Heizung" in massnahmen.
- auftraege_vergeben: true nur wenn der Kunde schreibt, dass schon beauftragt/unterschrieben wurde;
  false wenn er schreibt, dass noch nichts beauftragt ist; sonst null.
- frist: kurz zitieren, wenn es Eile oder einen Termin gibt (z. B. Notartermin), sonst null.
Antworte ausschließlich mit dem JSON-Objekt."""

SYSTEM_GLAETTEN = """Du überarbeitest E-Mail-Entwürfe eines Ingenieurbüros für Energieberatung.
Formuliere den Entwurf freundlicher und flüssiger, auf Deutsch, in der Sie-Form.
Strikte Regeln:
- Füge KEINE neuen Fakten, Preise, Termine, Fristen oder Zusagen hinzu.
- Behalte ALLE nummerierten Fragen und ALLE Punkte der Unterlagenliste bei.
- Behalte Anrede, Grußformel und Signatur bei.
Gib nur den fertigen E-Mail-Text zurück, ohne Betreff und ohne Erklärungen."""


@dataclass
class Ergebnis:
    anfrage: Anfrage
    fehlende_felder: list[str]
    rueckfragen: list[str]
    unterlagen: list[str]
    hinweise: list[str]
    betreff: str
    antwort: str
    prioritaet: str
    quelle: str
    dauer_s: float
    warnungen: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "anfrage": self.anfrage.to_dict(),
            "fehlende_felder": self.fehlende_felder,
            "rueckfragen": self.rueckfragen,
            "unterlagen": self.unterlagen,
            "interne_hinweise": self.hinweise,
            "prioritaet": self.prioritaet,
            "betreff": self.betreff,
            "antwort": self.antwort,
            "quelle": self.quelle,
            "dauer_s": round(self.dauer_s, 2),
            "warnungen": self.warnungen,
        }


def _nutzer_prompt(text: str) -> str:
    vorlage = json.dumps(KI_FELDER, ensure_ascii=False, indent=1)
    return f'Kundenanfrage:\n"""\n{text}\n"""\n\nGib ein JSON-Objekt mit genau diesen Feldern zurück:\n{vorlage}'


def _glaettung_ok(original: str, neu: str) -> bool:
    """Schutz gegen 'kreative' Modelle: Fragen und Listenpunkte müssen erhalten bleiben."""
    if not neu or len(neu) < 0.6 * len(original):
        return False
    if neu.count("?") < original.count("?"):
        return False
    return not any(z in neu for z in ("€", "Euro", "EUR"))


def analysiere(
    text: str,
    ki: KIEinstellungen | None = None,
    glaetten: bool = False,
    signatur: str = "Ihr Team der Energieberatung",
    ki_funktion: Callable[..., str] = frage_ki,
) -> Ergebnis:
    start = time.perf_counter()
    text = (text or "").strip()[:MAX_ZEICHEN]
    warnungen: list[str] = []

    regeln = analysiere_mit_regeln(text)
    anfrage = regeln
    quelle = "Regeln (ohne KI)"

    if ki is not None and text:
        try:
            roh = ki_funktion(ki, SYSTEM_EXTRAKTION, _nutzer_prompt(text), KI_JSON_SCHEMA)
            ki_anfrage = Anfrage.from_dict(lies_json(roh))
            ki_anfrage.betreff = regeln.betreff  # Betreff kommt immer aus dem Text
            anfrage = ergaenze(ki_anfrage, regeln)
            quelle = f"KI: {ki.anzeige} + Regeln"
        except KIFehler as e:
            warnungen.append(f"KI nicht verfügbar – Ergebnis nur mit Regeln. Grund: {e}")

    # Abgeleitete Angaben
    if anfrage.gebaeudetyp is None and (anfrage.wohneinheiten or 0) >= 3:
        anfrage.gebaeudetyp = "Mehrfamilienhaus"
    if anfrage.kundentyp is None:
        gewerblich = anfrage.unternehmen or anfrage.gebaeudetyp == "Nichtwohngebäude" or "energieaudit" in anfrage.leistungen
        anfrage.kundentyp = "gewerblich" if gewerblich else "privat"
    if not anfrage.leistungen:
        anfrage.leistungen = ["beratung"]

    entwurf = a.antwortentwurf(anfrage, signatur)
    if glaetten and ki is not None and not warnungen:
        try:
            neu = ki_funktion(ki, SYSTEM_GLAETTEN, entwurf, None).strip()
            if _glaettung_ok(entwurf, neu):
                entwurf = neu
            else:
                warnungen.append("Die KI-Glättung hat Inhalte verändert – es wird der Originalentwurf gezeigt.")
        except KIFehler as e:
            warnungen.append(f"Glätten nicht möglich: {e}")

    return Ergebnis(
        anfrage=anfrage,
        fehlende_felder=a.fehlende_felder(anfrage),
        rueckfragen=a.rueckfragen(anfrage),
        unterlagen=a.unterlagen(anfrage),
        hinweise=a.interne_hinweise(anfrage),
        betreff=a.betreff(anfrage),
        antwort=entwurf,
        prioritaet=a.prioritaet(anfrage),
        quelle=quelle,
        dauer_s=time.perf_counter() - start,
        warnungen=warnungen,
    )
