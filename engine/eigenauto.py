"""Eigenes Auto als Vergleichsmaßstab: Zeiträume und Zeitraumkosten (reine Funktionen)."""
from __future__ import annotations

import math
from collections import Counter
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
    kalender_bis: date | None = None   # ungekürztes Ende; geplante Fahrten zählen bis hierhin mit

    def __post_init__(self):
        if self.kalender_bis is None:
            self.kalender_bis = self.bis

    @property
    def tage(self) -> int:
        return max(0, (self.bis - self.von).days + 1)


@dataclass
class ZeitraumKosten:
    ist: float
    mit_profil: float
    differenz: float         # positiv: das eigene Auto wäre teurer gewesen


def zeitraum(art: str, bezug: date, heute: date, erster: date | None = None,
             letzter: date | None = None) -> Zeitraum:
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
        von, ende, label = erster or bezug, max(heute, letzter or heute), "Gesamt"
    else:
        raise ValueError(f"Unbekannte Zeitraumart: {art}")
    return Zeitraum(art, von, min(ende, heute), label, kalender_bis=ende)


def zeitraeume(art: str, eintraege: list[Eintrag], heute: date) -> list[Zeitraum]:
    """Alle Zeiträume mit mindestens einem Eintrag, neueste zuerst."""
    if not eintraege:
        return []
    tage = [e.start.date() for e in eintraege]
    if art == "gesamt":
        return [zeitraum("gesamt", min(tage), heute, erster=min(tage), letzter=max(tage))]
    gefunden = {}
    for t in tage:
        zr = zeitraum(art, t, heute)
        gefunden[zr.von] = zr
    return [gefunden[v] for v in sorted(gefunden, reverse=True)]


def zeitraumkosten(eintraege: list[Eintrag], profil: Profil, zr: Zeitraum) -> ZeitraumKosten:
    im_zeitraum = [e for e in eintraege if zr.von <= e.start.date() <= zr.kalender_bis]
    ist = sum(e.preis for e in im_zeitraum if e.gefahren)
    mit_profil = (profil.fix * zr.tage / 365
                  + sum(e.km * profil.variabel for e in im_zeitraum if e.eigenauto_gefahren)
                  + sum(e.preis for e in im_zeitraum if e.gefahren and not e.eigenauto_gefahren))
    ist, mit_profil = round(ist, 2), round(mit_profil, 2)
    return ZeitraumKosten(ist, mit_profil, round(mit_profil - ist, 2))


@dataclass
class BreakEven:
    status: str              # zu_wenig_daten | nie | bereits | schwelle
    schwelle_km: float | None = None
    km_jahr: float | None = None
    weitere_fahrten: int | None = None
    hochgerechnet: bool = False
    anlass: str | None = None


def break_even(eintraege: list[Eintrag], profil: Profil, heute: date) -> BreakEven:
    """Ab welcher Jahresfahrleistung das Profil günstiger wäre als das heutige Vorgehen."""
    fenster = [e for e in eintraege if heute - timedelta(days=365) < e.start.date() <= heute]
    basis = [e for e in fenster if e.eigenauto_gefahren and e.gefahren]
    km_basis = sum(e.km for e in basis)
    if len(basis) < 3 or km_basis <= 0:
        return BreakEven("zu_wenig_daten")
    if any(e.start.date() <= heute - timedelta(days=365) for e in eintraege):
        spanne = 365
    else:
        spanne = max(30, (heute - min(e.start.date() for e in fenster)).days)
    h = 365 / spanne
    p = sum(e.preis for e in basis) / km_basis
    if p <= profil.variabel:
        return BreakEven("nie")
    km_jahr = h * sum(e.km for e in fenster if e.eigenauto_gefahren)
    schwelle = profil.fix / (p - profil.variabel)
    if km_jahr >= schwelle:
        return BreakEven("bereits", round(schwelle, 2), round(km_jahr, 2), hochgerechnet=h > 1)
    n = math.ceil(round((schwelle - km_jahr) / (km_basis / len(basis)), 6))
    anlass = Counter(e.anlass for e in basis).most_common(1)[0][0]
    return BreakEven("schwelle", round(schwelle, 2), round(km_jahr, 2), n, h > 1, anlass)


def verlauf(eintraege: list[Eintrag], profile: list[Profil], heute: date) -> list[dict]:
    """Tagesweise kumulierte Kosten: heute gegen jedes Profil, vom ersten Eintrag bis heute."""
    if not eintraege:
        return []
    erster = min(e.start.date() for e in eintraege)
    zeilen = []
    for i in range((heute - erster).days + 1):
        d = erster + timedelta(days=i)
        bis_d = [e for e in eintraege if e.start.date() <= d]
        zeilen.append({"datum": d, "reihe": "Heute",
                       "kumuliert": round(sum(e.preis for e in bis_d if e.gefahren), 2)})
        for pr in profile:
            wert = (pr.fix * (i + 1) / 365
                    + sum(e.km * pr.variabel for e in bis_d if e.eigenauto_gefahren)
                    + sum(e.preis for e in bis_d if e.gefahren and not e.eigenauto_gefahren))
            zeilen.append({"datum": d, "reihe": pr.name, "kumuliert": round(wert, 2)})
    return zeilen
