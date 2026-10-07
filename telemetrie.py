"""Ereignisse an das zentrale Logging (tool-log) senden – im Hintergrund, Ausfälle stören die App nicht.

Konfiguration über Umgebungsvariablen: TOOLLOG_API_KEY (ohne Key ist das Logging aus),
TOOLLOG_API_URL (Standard: tool-log-api im gemeinsamen Docker-Netz), TOOLLOG_INSTANZ (Domain der Instanz)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import urllib.request
from collections.abc import MutableMapping

from engine import Eintrag, Ergebnis, Szenario

TOOL = "mobil-vergleich"
VERSION = "1.2.0"
STANDARD_URL = "http://tool-log-api:8000/api/log"
TIMEOUT_S = 2

log = logging.getLogger(__name__)


def vergleich_daten(sz: Szenario, vorlage: str | None, angebote: dict[str, float],
                    ergebnisse: list[Ergebnis]) -> dict:
    """Ein Vergleich: Reise, Annahmen, eingetragene Angebote und die Rangliste."""
    rangliste = [{"anbieter": e.anbieter, "option": e.option, "gruppe": e.gruppe, "gesamt": e.gesamt}
                 for e in ergebnisse]
    return {
        "start": sz.start.isoformat(), "ende": sz.ende.isoformat(), "stunden": round(sz.stunden, 2),
        "km": sz.km, "hund": sz.hund, "km_paket": sz.km_paket_nutzen,
        "selbstbehalt_reduziert": sz.selbstbehalt_reduzieren, "spritpreis": sz.spritpreis,
        "vorlage": vorlage, "angebote": angebote, "rangliste": rangliste,
        "guenstigste": {k: rangliste[0][k] for k in ("anbieter", "option", "gesamt")} if rangliste else None,
    }


def entscheidung_daten(e: Eintrag) -> dict:
    return {"start": e.start.isoformat(), "ende": e.ende.isoformat(), "anlass": e.anlass, "ergebnis": e.ergebnis,
            "gruppe": e.gruppe, "preis_geplant": e.preis_geplant, "km_geplant": e.km_geplant,
            "eigenauto_gefahren": e.eigenauto_gefahren}


def neu_in_sitzung(sitzung: MutableMapping, event: str, daten: dict) -> bool:
    """True beim ersten Mal je Ereignis und Inhalt in dieser Sitzung – Streamlit rechnet bei jeder Eingabe neu."""
    fingerabdruck = hashlib.sha256(json.dumps([event, daten], sort_keys=True, default=str).encode()).hexdigest()
    gesendet = sitzung.setdefault("_telemetrie_gesendet", set())
    if fingerabdruck in gesendet:
        return False
    gesendet.add(fingerabdruck)
    return True


def _post(url: str, schluessel: str, nachricht: dict) -> None:
    anfrage = urllib.request.Request(url, data=json.dumps(nachricht).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Api-Key": schluessel})
    try:
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT_S) as antwort:
            antwort.read()
    except Exception as fehler:   # Netz, Timeout, 4xx/5xx – nur protokollieren
        log.warning("tool-log: %s nicht gesendet: %s", nachricht["event"], fehler)


def senden(event: str, daten: dict) -> threading.Thread | None:
    """Sendet im Hintergrund; ohne TOOLLOG_API_KEY passiert nichts (Rückgabe None)."""
    schluessel = os.environ.get("TOOLLOG_API_KEY")
    if not schluessel:
        return None
    nachricht = {"tool": TOOL, "tool_version": VERSION, "instance": os.environ.get("TOOLLOG_INSTANZ", TOOL),
                 "event": event, "payload": daten}
    faden = threading.Thread(target=_post, args=(os.environ.get("TOOLLOG_API_URL", STANDARD_URL), schluessel,
                                                 nachricht), daemon=True)
    faden.start()
    return faden
