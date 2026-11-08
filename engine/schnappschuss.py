"""Schnappschuss einer Entscheidung: Szenario, Rangliste und Tarifstand – nur JSON-Typen."""
from __future__ import annotations

from .modelle import Ergebnis, Szenario


def schnappschuss(sz: Szenario, ergebnisse: list[Ergebnis], tarife: dict) -> dict:
    return {
        "szenario": {"start": sz.start.isoformat(), "ende": sz.ende.isoformat(), "km": sz.km,
                     "spritpreis": sz.spritpreis, "hund": sz.hund, "km_paket_nutzen": sz.km_paket_nutzen,
                     "selbstbehalt_reduzieren": sz.selbstbehalt_reduzieren},
        "rangliste": [{"anbieter": e.anbieter, "option": e.option, "gruppe": e.gruppe,
                       "gesamt": e.gesamt, "posten": dict(e.posten)} for e in ergebnisse],
        "tarifstand": {t["name"]: str(t["stand"]) for t in tarife["carsharing"]},
    }
