"""Gemeinsame Schnittstelle für alle Preis-Abrufer.

Regeln für Phase 2:
- Ein Fetcher liefert einen MietAngebot-Vorschlag oder wirft FetchFehler.
- Er läuft NIE im Streamlit-Request, sondern in einem eigenen Container/Job
  und schreibt Ergebnisse mit Zeitstempel in einen Cache (z. B. SQLite).
- Die App liest nur den Cache und fällt sonst auf manuelle Eingabe zurück.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from engine.modelle import MietAngebot, Szenario


class FetchFehler(RuntimeError):
    pass


class Fetcher(ABC):
    id: str = ""
    name: str = ""
    aktiv: bool = False   # erst auf True setzen, wenn der Abruf zuverlässig läuft

    @abstractmethod
    def hole_angebot(self, sz: Szenario, station: str, fahrzeugklasse: str) -> MietAngebot:
        """Günstigstes passendes Angebot für das Szenario holen."""
