"""Datenmodelle: was wir rechnen wollen und was herauskommt."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Szenario:
    start: datetime
    ende: datetime
    km: float
    spritpreis: float = 1.75          # €/l, nur für Optionen ohne Sprit inklusive
    hund: bool = True
    km_paket_nutzen: bool = True      # scouter 500-km-Paket
    selbstbehalt_reduzieren: bool = False

    @property
    def minuten(self) -> int:
        return max(0, int((self.ende - self.start).total_seconds() // 60))

    @property
    def stunden(self) -> float:
        return self.minuten / 60


@dataclass
class MietAngebot:
    """Ein konkretes Angebot (Sixt, Europcar, Getaround) für genau diese Reise."""
    id: str
    name: str
    preis_gesamt: float                 # Mietpreis laut Angebot inkl. Gebühren
    frei_km: float = 0                  # 0 = unbegrenzt
    mehr_km_preis: float = 0.0
    verbrauch_l_100km: float = 6.5
    extras: float = 0.0                 # z. B. Reinigung wegen Hund, Zusatzfahrer
    haustiere: str = "pruefen"
    quelle: str = "manuell"             # manuell | automatisch


@dataclass
class BahnAngebot:
    preis_gesamt: float                 # Familie + Hund, hin und zurück
    vor_ort: float = 0.0                # Taxi/ÖPNV/Carsharing am Ziel
    haustiere: str = "ja"


@dataclass
class Ergebnis:
    anbieter: str
    option: str
    gruppe: str                          # Carsharing | Mietwagen | Bahn
    gesamt: float
    posten: dict[str, float] = field(default_factory=dict)
    hinweise: list[str] = field(default_factory=list)
    haustiere: str = "pruefen"
    unsicher: bool = False               # True, wenn unverifizierte Tarifwerte genutzt wurden


NICHT_GEFAHREN = "nicht gefahren"


@dataclass
class Eintrag:
    """Eine gespeicherte Fahrt bzw. Entscheidung im Entscheidungslog."""
    start: datetime
    ende: datetime
    anlass: str
    ergebnis: str                        # Anbieter und Option oder NICHT_GEFAHREN
    gruppe: str                          # Carsharing | Mietwagen | Bahn | Sonstiges | keine
    km_geplant: float
    preis_geplant: float
    eigenauto_gefahren: bool             # "Mit eigenem Auto wären wir gefahren"
    km_tatsaechlich: float | None = None
    preis_tatsaechlich: float | None = None
    vergleich: dict | None = None        # Schnappschuss der Rangliste
    id: int | None = None
    angelegt_am: datetime | None = None

    @property
    def km(self) -> float:
        return self.km_geplant if self.km_tatsaechlich is None else self.km_tatsaechlich

    @property
    def preis(self) -> float:
        return self.preis_geplant if self.preis_tatsaechlich is None else self.preis_tatsaechlich

    @property
    def gefahren(self) -> bool:
        return self.ergebnis != NICHT_GEFAHREN

    def rechnung_offen(self, jetzt: datetime) -> bool:
        return self.gefahren and self.preis_tatsaechlich is None and self.ende < jetzt


@dataclass
class Profil:
    """Referenzprofil für ein eigenes Auto (Kosten pro Jahr fix, pro km variabel)."""
    id: str
    name: str
    quelle: str
    stand: str
    fix_pro_jahr: dict[str, float]
    variabel_pro_km: dict[str, float]
    hundetauglich: bool = True
    unverifiziert: list[str] = field(default_factory=list)

    @property
    def fix(self) -> float:
        return sum(self.fix_pro_jahr.values())

    @property
    def variabel(self) -> float:
        return sum(self.variabel_pro_km.values())
