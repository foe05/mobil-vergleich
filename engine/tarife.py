"""Tarif-YAMLs laden."""
from __future__ import annotations

from pathlib import Path

import yaml


def lade_tarife(ordner: str | Path) -> dict:
    ordner = Path(ordner)
    carsharing, angebote = [], {}
    for datei in sorted(ordner.glob("*.yaml")):
        daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
        if datei.stem == "angebote":
            angebote = daten
        elif daten.get("typ") == "carsharing":
            carsharing.append(daten)
    return {"carsharing": carsharing, "angebote": angebote}
