"""Eigenes Auto als Vergleichsmaßstab: Zeiträume und Zeitraumkosten (reine Funktionen)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .modelle import Eintrag, Profil

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


@dataclass
class Zeitraum:
    art: str                 # monat | quartal | jahr | gesamt
    von: date
    bis: date
    label: str

    @property
    def tage(self) -> int:
        return (self.bis - self.von).days + 1


@dataclass
class ZeitraumKosten:
    ist: float
    mit_profil: float
    differenz: float         # positiv: das eigene Auto wäre teurer gewesen


def zeitraum(art: str, bezug: date, heute: date, erster: date | None = None) -> Zeitraum:
    """Kalenderzeitraum, der `bezug` enthält; ein laufender Zeitraum endet heute."""
    if art == "monat":
        von = date(bezug.year, bezug.month, 1)
        ende = (date(bezug.year + bezug.month // 12, bezug.month % 12 + 1, 1)) - timedelta(days=1)
        label = f"{MONATE[bezug.month - 1]} {bezug.year}"
    elif art == "quartal":
        q = (bezug.month - 1) // 3
        von = date(bezug.year, q * 3 + 1, 1)
        ende = date(bezug.year + (q == 3), (q * 3 + 4 - 1) % 12 + 1, 1) - timedelta(days=1)
        label = f"Q{q + 1} {bezug.year}"
    elif art == "jahr":
        von, ende, label = date(bezug.year, 1, 1), date(bezug.year, 12, 31), str(bezug.year)
    elif art == "gesamt":
        von, ende, label = erster or bezug, heute, "Gesamt"
    else:
        raise ValueError(f"Unbekannte Zeitraumart: {art}")
    return Zeitraum(art, von, min(ende, heute), label)


def zeitraeume(art: str, eintraege: list[Eintrag], heute: date) -> list[Zeitraum]:
    """Alle Zeiträume mit mindestens einem Eintrag, neueste zuerst."""
    if not eintraege:
        return []
    tage = [e.start.date() for e in eintraege]
    if art == "gesamt":
        return [zeitraum("gesamt", min(tage), heute, erster=min(tage))]
    gefunden = {zeitraum(art, t, heute).von: zeitraum(art, t, heute) for t in tage}
    return [gefunden[v] for v in sorted(gefunden, reverse=True)]


def zeitraumkosten(eintraege: list[Eintrag], profil: Profil, zr: Zeitraum) -> ZeitraumKosten:
    im_zeitraum = [e for e in eintraege if zr.von <= e.start.date() <= zr.bis]
    ist = sum(e.preis for e in im_zeitraum if e.gefahren)
    mit_profil = (profil.fix * zr.tage / 365
                  + sum(e.km * profil.variabel for e in im_zeitraum if e.eigenauto_gefahren)
                  + sum(e.preis for e in im_zeitraum if e.gefahren and not e.eigenauto_gefahren))
    ist, mit_profil = round(ist, 2), round(mit_profil, 2)
    return ZeitraumKosten(ist, mit_profil, round(mit_profil - ist, 2))
