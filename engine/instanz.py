"""Einstellungen je Instanz (tarife/instanz.yaml): Ort, Reisende, Hund, Reise-Vorlagen.

Fehlt die Datei, gelten die Werte der ersten Instanz (Kassel, vier Personen mit Hund)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

TAGE = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}


@dataclass
class Vorlage:
    name: str
    start_tag: int          # 0 = Montag … 6 = Sonntag; Reise beginnt am nächsten solchen Tag
    start: time
    tage: int               # Rückgabe so viele Tage nach dem Start
    ende: time
    km: int


def _standard_vorlagen() -> list[Vorlage]:
    return [
        Vorlage("IKEA-Nachmittag", 5, time(13), 0, time(17), 30),
        Vorlage("Oma (1 Nacht)", 5, time(10), 1, time(16), 100),
        Vorlage("Langes Wochenende", 4, time(14), 3, time(18), 700),
        Vorlage("Urlaub (2 Wochen)", 5, time(8), 14, time(18), 1500),
    ]


@dataclass
class Instanz:
    ort: str = "Kassel"
    personen: int = 4
    hund: bool = True
    vorlagen: list[Vorlage] = field(default_factory=_standard_vorlagen)


def _uhrzeit(wert) -> time:
    if isinstance(wert, int):            # YAML liest 10:00 ohne Anführungszeichen als Minuten (600)
        return time(wert // 60, wert % 60)
    return datetime.strptime(str(wert), "%H:%M").time()


def _vorlage(d: dict) -> Vorlage:
    return Vorlage(str(d["name"]), TAGE[str(d["start_tag"]).lower()[:2]], _uhrzeit(d["start"]),
                   int(d["tage"]), _uhrzeit(d["ende"]), int(d["km"]))


def lade_instanz(ordner: str | Path) -> tuple[Instanz, list[str]]:
    """Instanz und Hinweise zu übersprungenen Teilen; Fehler führen nie zum Absturz."""
    datei = Path(ordner) / "instanz.yaml"
    if not datei.exists():
        return Instanz(), []
    try:
        daten = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
        if not isinstance(daten, dict):
            raise ValueError("kein Schlüssel-Wert-Inhalt")
        standard = Instanz()
        i = Instanz(ort=str(daten.get("ort", standard.ort)), personen=int(daten.get("personen", standard.personen)),
                    hund=bool(daten.get("hund", standard.hund)))
    except (OSError, yaml.YAMLError, ValueError, TypeError) as fehler:
        return Instanz(), [f"instanz.yaml konnte nicht gelesen werden, es gelten die Standardwerte: {fehler}"]

    hinweise = []
    if "vorlagen" in daten:
        i.vorlagen = []
        for d in daten["vorlagen"] or []:
            try:
                i.vorlagen.append(_vorlage(d))
            except (KeyError, ValueError, TypeError) as fehler:
                name = d.get("name", "?") if isinstance(d, dict) else d
                hinweise.append(f"Vorlage „{name}“ in instanz.yaml übersprungen: {fehler!r}")
    return i, hinweise


def reisende_text(i: Instanz) -> str:
    personen = f"{i.personen} Person" + ("en" if i.personen != 1 else "")
    return f"{personen} und Hund" if i.hund else personen


def vorlage_zeiten(v: Vorlage, heute: date) -> tuple[date, time, date, time, int]:
    """Start am nächsten passenden Wochentag (heute zählt nicht), Rückgabe `tage` später."""
    start = heute + timedelta(days=(v.start_tag - heute.weekday()) % 7 or 7)
    return start, v.start, start + timedelta(days=v.tage), v.ende, v.km
