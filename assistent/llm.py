"""Anbindung an Sprachmodelle: lokal mit Ollama (kostenlos) oder per API (Claude, OpenAI).

Bewusst nur mit ``requests`` umgesetzt, ohne weitere SDKs – so bleibt das
Projekt klein und leicht zu installieren.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

STANDARD_MODELLE = {
    "ollama": "llama3.2",
    "claude": "claude-haiku-5-5",
    "openai": "gpt-5-mini",
}


class KIFehler(Exception):
    """Verständliche Fehlermeldung für die Oberfläche."""


@dataclass
class KIEinstellungen:
    anbieter: str  # "ollama" | "claude" | "openai"
    modell: str = ""
    api_key: str | None = None
    ollama_url: str = "http://localhost:11434"
    timeout: int = 180

    @property
    def anzeige(self) -> str:
        namen = {"ollama": "Ollama (lokal)", "claude": "Claude", "openai": "OpenAI"}
        return f"{namen.get(self.anbieter, self.anbieter)} · {self.modell or STANDARD_MODELLE.get(self.anbieter, '')}"


def ollama_modelle(url: str = "http://localhost:11434") -> list[str] | None:
    """Liste der installierten Ollama-Modelle, oder None wenn Ollama nicht läuft."""
    try:
        r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=2)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError, KeyError):
        return None


def frage_ki(einst: KIEinstellungen, system: str, nutzer: str, json_schema: dict | None = None) -> str:
    """Schickt eine Anfrage an das gewählte Modell und gibt den Antworttext zurück."""
    modell = einst.modell or STANDARD_MODELLE.get(einst.anbieter, "")
    try:
        if einst.anbieter == "ollama":
            return _ollama(einst, modell, system, nutzer, json_schema)
        if einst.anbieter == "claude":
            return _claude(einst, modell, system, nutzer)
        if einst.anbieter == "openai":
            return _openai(einst, modell, system, nutzer, json_modus=json_schema is not None)
    except requests.Timeout as e:
        raise KIFehler("Das Modell hat zu lange gebraucht (Zeitüberschreitung). Ein kleineres Modell hilft.") from e
    except requests.ConnectionError as e:
        if einst.anbieter == "ollama":
            raise KIFehler("Ollama ist nicht erreichbar. Bitte Ollama starten (siehe README).") from e
        raise KIFehler("Keine Internetverbindung zur KI-Schnittstelle.") from e
    raise KIFehler(f"Unbekannter Anbieter: {einst.anbieter}")


def _ollama(einst: KIEinstellungen, modell: str, system: str, nutzer: str, json_schema: dict | None) -> str:
    url = f"{einst.ollama_url.rstrip('/')}/api/chat"
    nutzlast = {
        "model": modell,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": nutzer}],
        "stream": False,
        "options": {"temperature": 0},
    }
    if json_schema is not None:
        nutzlast["format"] = json_schema
    r = requests.post(url, json=nutzlast, timeout=einst.timeout)
    if r.status_code == 404:
        raise KIFehler(f"Modell „{modell}“ ist nicht installiert. Im Terminal: ollama pull {modell}")
    if r.status_code >= 400 and json_schema is not None:
        # Ältere Ollama-Versionen kennen kein JSON-Schema – dann einfacher JSON-Modus.
        nutzlast["format"] = "json"
        r = requests.post(url, json=nutzlast, timeout=einst.timeout)
    if r.status_code >= 400:
        raise KIFehler(f"Ollama-Fehler {r.status_code}: {r.text[:200]}")
    return r.json()["message"]["content"]


def _claude(einst: KIEinstellungen, modell: str, system: str, nutzer: str) -> str:
    if not einst.api_key:
        raise KIFehler("Bitte einen Claude-API-Schlüssel eingeben.")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": einst.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": modell,
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": nutzer}],
        },
        timeout=einst.timeout,
    )
    _pruefe_api_antwort(r, "Claude")
    return "".join(block.get("text", "") for block in r.json().get("content", []) if block.get("type") == "text")


def _openai(einst: KIEinstellungen, modell: str, system: str, nutzer: str, json_modus: bool) -> str:
    if not einst.api_key:
        raise KIFehler("Bitte einen OpenAI-API-Schlüssel eingeben.")
    nutzlast = {
        "model": modell,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": nutzer}],
    }
    if json_modus:
        nutzlast["response_format"] = {"type": "json_object"}
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {einst.api_key}"},
        json=nutzlast,
        timeout=einst.timeout,
    )
    _pruefe_api_antwort(r, "OpenAI")
    return r.json()["choices"][0]["message"]["content"] or ""


def _pruefe_api_antwort(r: requests.Response, name: str) -> None:
    if r.status_code in (401, 403):
        raise KIFehler(f"{name}: API-Schlüssel ungültig oder ohne Berechtigung.")
    if r.status_code == 404:
        raise KIFehler(f"{name}: Modell nicht gefunden. Bitte den Modellnamen prüfen.")
    if r.status_code == 429:
        raise KIFehler(f"{name}: Limit erreicht oder kein Guthaben. Später erneut versuchen.")
    if r.status_code >= 400:
        raise KIFehler(f"{name}-Fehler {r.status_code}: {r.text[:200]}")


def lies_json(text: str) -> dict:
    """Holt ein JSON-Objekt aus einer Modellantwort – auch wenn drumherum Text oder ```-Blöcke stehen."""
    if not text:
        raise KIFehler("Die KI hat eine leere Antwort geliefert.")
    sauber = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        daten = json.loads(sauber)
    except json.JSONDecodeError:
        start, ende = sauber.find("{"), sauber.rfind("}")
        if start == -1 or ende <= start:
            raise KIFehler("Die KI-Antwort enthielt kein gültiges JSON.") from None
        try:
            daten = json.loads(sauber[start : ende + 1])
        except json.JSONDecodeError as e:
            raise KIFehler("Die KI-Antwort enthielt kein gültiges JSON.") from e
    if not isinstance(daten, dict):
        raise KIFehler("Die KI-Antwort war kein JSON-Objekt.")
    return daten
