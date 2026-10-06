"""Tarif-YAMLs laden."""
from __future__ import annotations

from pathlib import Path

import yaml

from .modelle import Profil

PROFIL_PFLICHT = ("id", "name", "quelle", "stand", "fix_pro_jahr", "variabel_pro_km")


def _lade_profile(daten: dict, hinweise: list[str]) -> list[Profil]:
    profile = []
    for roh in daten.get("profile") or []:
        fehlt = next((f for f in PROFIL_PFLICHT if not roh.get(f)), None)
        if fehlt:
            hinweise.append(f"Profil „{roh.get('name') or roh.get('id')}“ übersprungen: {fehlt} fehlt")
            continue
        profile.append(Profil(
            id=roh["id"], name=roh["name"], quelle=roh["quelle"], stand=str(roh["stand"]),
            fix_pro_jahr=dict(roh["fix_pro_jahr"]), variabel_pro_km=dict(roh["variabel_pro_km"]),
            hundetauglich=bool(roh.get("hundetauglich", True)),
            unverifiziert=list(roh.get("unverifiziert") or []),
        ))
    return profile


def lade_tarife(ordner: str | Path) -> dict:
    ordner = Path(ordner)
    carsharing, angebote, eigenauto, hinweise = [], {}, [], []
    for datei in sorted(ordner.glob("*.yaml")):
        daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
        if datei.stem == "angebote":
            angebote = daten
        elif daten.get("typ") == "carsharing":
            carsharing.append(daten)
        elif daten.get("typ") == "eigenauto":
            eigenauto += _lade_profile(daten, hinweise)
    return {"carsharing": carsharing, "angebote": angebote, "eigenauto": eigenauto, "hinweise": hinweise}
