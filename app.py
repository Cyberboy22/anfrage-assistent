"""Anfrage-Assistent – Oberfläche (Streamlit).

Start:  streamlit run app.py   (oder start_windows.bat / start_mac.command)
"""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

import streamlit as st

from assistent.leistungen import FELD_LABELS, LEISTUNGEN
from assistent.llm import STANDARD_MODELLE, KIEinstellungen, ollama_modelle
from assistent.pipeline import Ergebnis, analysiere

st.set_page_config(page_title="Anfrage-Assistent Energieberatung", page_icon="📨", layout="wide")

BEISPIEL_ORDNER = Path(__file__).parent / "beispiele"
MODI = {
    "regeln": "Ohne KI (Regeln, sofort)",
    "ollama": "Lokal mit Ollama (kostenlos)",
    "claude": "Claude (API-Schlüssel)",
    "openai": "ChatGPT / OpenAI (API-Schlüssel)",
}
ANZEIGE_FELDER = (
    "name", "email", "telefon", "kundentyp", "unternehmen", "gebaeudetyp", "baujahr",
    "wohnflaeche_m2", "wohneinheiten", "heizung", "ort", "massnahmen", "zeitplan",
    "auftraege_vergeben", "anlass_ausweis", "frist",
)  # fmt: skip


@st.cache_data(show_spinner=False)
def lade_beispiele() -> dict[str, str]:
    beispiele: dict[str, str] = {}
    for datei in sorted(BEISPIEL_ORDNER.glob("*.txt")):
        text = datei.read_text(encoding="utf-8")
        erste = text.splitlines()[0] if text else datei.stem
        titel = erste.split(":", 1)[1].strip() if erste.lower().startswith("betreff:") else datei.stem
        beispiele[titel] = text
    return beispiele


@st.cache_data(ttl=15, show_spinner=False)
def ollama_status(url: str) -> list[str] | None:
    return ollama_modelle(url)


def wert_anzeigen(ergebnis: Ergebnis, feld: str) -> str | None:
    a = ergebnis.anfrage
    if feld == "ort":
        return " ".join(x for x in (a.plz, a.ort) if x) or None
    wert = getattr(a, feld)
    if wert is None or wert == []:
        return None
    if feld == "wohnflaeche_m2":
        return f"{wert:,.0f} m²".replace(",", ".")
    if isinstance(wert, bool):
        return "Ja" if wert else "Nein"
    if isinstance(wert, list):
        return ", ".join(wert)
    return str(wert)


def beispiel_laden() -> None:
    wahl = st.session_state.get("beispiel_wahl")
    if wahl and wahl in lade_beispiele():
        st.session_state.anfrage_text = lade_beispiele()[wahl]
        st.session_state.pop("ergebnis", None)


# --- Seitenleiste ---------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Einstellungen")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    modelle = ollama_status(ollama_url)
    start_modus = "ollama" if modelle else "regeln"

    modus = st.radio(
        "Wie soll die Anfrage gelesen werden?",
        options=list(MODI),
        format_func=MODI.get,
        index=list(MODI).index(start_modus),
    )

    ki: KIEinstellungen | None = None
    if modus == "ollama":
        if modelle is None:
            st.warning("Ollama läuft nicht. Ollama installieren und starten – bis dahin wird mit Regeln gearbeitet.")
        elif not modelle:
            st.warning(f"Noch kein Modell installiert. Im Terminal: `ollama pull {STANDARD_MODELLE['ollama']}`")
        else:
            standard = next((m for m in modelle if m.startswith(STANDARD_MODELLE["ollama"])), modelle[0])
            modell = st.selectbox("Modell", modelle, index=modelle.index(standard))
            ki = KIEinstellungen("ollama", modell=modell, ollama_url=ollama_url)
            st.success("Läuft lokal – keine Daten verlassen diesen Rechner.", icon="🔒")
    elif modus in ("claude", "openai"):
        env = "ANTHROPIC_API_KEY" if modus == "claude" else "OPENAI_API_KEY"
        modell = st.text_input("Modell", value=STANDARD_MODELLE[modus])
        schluessel = st.text_input("API-Schlüssel", value=os.environ.get(env, ""), type="password")
        st.caption("Der Schlüssel wird nicht gespeichert. Die Anfrage wird zur Analyse an den Anbieter gesendet.")
        if schluessel:
            ki = KIEinstellungen(modus, modell=modell, api_key=schluessel)
        else:
            st.info("Ohne Schlüssel wird mit Regeln gearbeitet.")

    glaetten = False
    if ki is not None:
        glaetten = st.checkbox(
            "Antwort von der KI sprachlich glätten",
            help="Die KI formuliert den Entwurf flüssiger. Neue Fakten, Preise oder Termine sind verboten – "
            "verändert sie Inhalte, wird automatisch der Originalentwurf verwendet.",
        )

    signatur = st.text_area("Signatur im Antwortentwurf", value="Ihr Team der Energieberatung", height=80)

    st.divider()
    st.caption(
        "**Leistungen im Katalog:** "
        + ", ".join(v.name for k, v in LEISTUNGEN.items() if k != "beratung")
        + ". Anpassbar in `assistent/leistungen.py`."
    )

# --- Hauptbereich ------------------------------------------------------------------

st.title("📨 Anfrage-Assistent für die Energieberatung")
st.caption(
    "Kundenanfrage einfügen → gewünschte Leistung, Eckdaten, fehlende Angaben und ein fertiger Antwortentwurf. "
    "Alle Beispiel-Anfragen sind erfunden."
)

links, rechts = st.columns([2, 3], gap="large")

with links:
    st.subheader("1 · Anfrage")
    st.selectbox(
        "Beispiel laden",
        options=list(lade_beispiele()),
        index=None,
        placeholder="Eine Beispiel-Anfrage wählen …",
        key="beispiel_wahl",
        on_change=beispiel_laden,
    )
    st.text_area(
        "E-Mail-Text der Kundin / des Kunden",
        key="anfrage_text",
        height=420,
        placeholder="Hier die Kunden-E-Mail einfügen (Strg+V) …",
    )
    if st.button("🔍 Anfrage analysieren", type="primary", width="stretch"):
        text = st.session_state.get("anfrage_text", "").strip()
        if len(text) < 20:
            st.warning("Bitte zuerst eine Anfrage einfügen oder ein Beispiel laden.")
        else:
            with st.spinner("Lese die Anfrage …" if ki is None else "Die KI liest die Anfrage …"):
                st.session_state.ergebnis = analysiere(text, ki=ki, glaetten=glaetten, signatur=signatur)
                st.session_state.lauf = st.session_state.get("lauf", 0) + 1

with rechts:
    st.subheader("2 · Ergebnis")
    ergebnis: Ergebnis | None = st.session_state.get("ergebnis")

    if ergebnis is None:
        st.info("Links ein Beispiel laden oder eine eigene Anfrage einfügen und auf **Anfrage analysieren** klicken.")
    else:
        for w in ergebnis.warnungen:
            st.warning(w)

        badges = " ".join(f":green-badge[{LEISTUNGEN[k].name}]" for k in ergebnis.anfrage.leistungen)
        st.markdown(f"**Gewünschte Leistung:** {badges}")

        m1, m2, m3 = st.columns(3)
        m1.metric("Priorität", "🔴 hoch" if ergebnis.prioritaet == "hoch" else "🟢 normal")
        m2.metric("Rückfragen", len(ergebnis.rueckfragen))
        dauer = "< 0,1 s" if ergebnis.dauer_s < 0.1 else f"{ergebnis.dauer_s:.1f} s".replace(".", ",")
        m3.metric("Dauer", dauer)
        st.caption(f"Analysiert mit: {ergebnis.quelle}")

        for h in ergebnis.hinweise:
            st.info(h, icon="💡")

        tab_daten, tab_fragen, tab_antwort, tab_export = st.tabs(
            ["📋 Eckdaten", "❓ Rückfragen & Unterlagen", "✉️ Antwortentwurf", "🧾 Export"]
        )

        with tab_daten:
            zeilen = []
            for feld in ANZEIGE_FELDER:
                wert = wert_anzeigen(ergebnis, feld)
                if wert is not None:
                    zeilen.append({"Angabe": FELD_LABELS[feld], "Wert": wert, "Status": "✅ erkannt"})
                elif feld in ergebnis.fehlende_felder:
                    zeilen.append({"Angabe": FELD_LABELS[feld], "Wert": "–", "Status": "❓ fehlt → Rückfrage"})
            st.dataframe(zeilen, hide_index=True, width="stretch")

        with tab_fragen:
            st.markdown("**Rückfragen an den Kunden**")
            if ergebnis.rueckfragen:
                st.markdown("\n".join(f"{i}. {f}" for i, f in enumerate(ergebnis.rueckfragen, 1)))
            else:
                st.success("Alle nötigen Angaben sind vorhanden.")
            st.markdown("**Benötigte Unterlagen**")
            st.markdown("\n".join(f"- {u}" for u in ergebnis.unterlagen) or "–")

        with tab_antwort:
            lauf = st.session_state.get("lauf", 0)
            betreff = st.text_input("Betreff", value=ergebnis.betreff, key=f"betreff_{lauf}")
            text = st.text_area("Text (bearbeitbar)", value=ergebnis.antwort, height=460, key=f"antwort_{lauf}")
            empfaenger = ergebnis.anfrage.email or ""
            mailto = "mailto:{}?subject={}&body={}".format(
                urllib.parse.quote(empfaenger), urllib.parse.quote(betreff), urllib.parse.quote(text)
            )
            b1, b2 = st.columns(2)
            b1.link_button("📧 Im E-Mail-Programm öffnen", mailto, width="stretch")
            b2.download_button(
                "⬇️ Als Textdatei speichern",
                data=f"An: {empfaenger}\nBetreff: {betreff}\n\n{text}",
                file_name="antwortentwurf.txt",
                width="stretch",
            )
            st.caption("Der Entwurf wird nie automatisch verschickt – er wird immer erst von einem Menschen geprüft.")

        with tab_export:
            st.caption("Strukturierte Daten, z. B. für eine Kundenliste oder ein CRM.")
            daten = ergebnis.to_dict()
            st.json(daten, expanded=False)
            st.download_button(
                "⬇️ JSON herunterladen",
                data=json.dumps(daten, ensure_ascii=False, indent=2),
                file_name="anfrage.json",
                mime="application/json",
            )

with st.expander("ℹ️ So funktioniert der Assistent"):
    st.markdown(
        """
1. **Regeln** erkennen sofort typische Angaben (Baujahr, m², Heizung, PLZ, Telefon …) – ganz ohne KI.
2. **Optional liest ein Sprachmodell** die Anfrage und liefert die Angaben als JSON. Lokal mit Ollama
   verlassen keine Kundendaten den Rechner (DSGVO). KI-Werte haben Vorrang, Lücken füllen die Regeln.
3. Jede Angabe wird **geprüft und normalisiert** (z. B. Baujahr zwischen 1800 und heute) – unplausible Werte fliegen raus.
4. Abgleich mit dem **Leistungskatalog**: Was braucht das Büro für einen iSFP, einen Energieausweis …?
   Fehlende Angaben werden zu Rückfragen, dazu kommt eine Unterlagen-Checkliste.
5. Der **Antwortentwurf** entsteht aus einer Vorlage und enthält nur Angaben aus der Anfrage –
   keine erfundenen Preise, Termine oder Zusagen.
"""
    )
