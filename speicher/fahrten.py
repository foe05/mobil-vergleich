"""Einziger SQLite-Zugriff: Schema, anlegen, ändern, löschen, abfragen."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from engine import Eintrag

SCHEMA = """
CREATE TABLE IF NOT EXISTS eintraege (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    angelegt_am TEXT NOT NULL,
    start TEXT NOT NULL,
    ende TEXT NOT NULL,
    anlass TEXT NOT NULL,
    ergebnis TEXT NOT NULL,
    gruppe TEXT NOT NULL,
    km_geplant REAL NOT NULL,
    km_tatsaechlich REAL,
    preis_geplant REAL NOT NULL,
    preis_tatsaechlich REAL,
    eigenauto_gefahren INTEGER NOT NULL,
    vergleich TEXT
)
"""

_FELDER = ("start", "ende", "anlass", "ergebnis", "gruppe", "km_geplant", "km_tatsaechlich",
           "preis_geplant", "preis_tatsaechlich", "eigenauto_gefahren", "vergleich")


def db_pfad() -> Path:
    return Path(os.environ.get("MOBIL_DB", "/app/daten/mobil.db"))


def oeffnen(pfad: Path) -> sqlite3.Connection:
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(pfad, check_same_thread=False, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(SCHEMA)
    con.execute("PRAGMA user_version=1")
    con.commit()
    return con


def _werte(e: Eintrag) -> tuple:
    return (e.start.isoformat(), e.ende.isoformat(), e.anlass, e.ergebnis, e.gruppe,
            e.km_geplant, e.km_tatsaechlich, e.preis_geplant, e.preis_tatsaechlich,
            int(e.eigenauto_gefahren),
            None if e.vergleich is None else json.dumps(e.vergleich, ensure_ascii=False))


def anlegen(con: sqlite3.Connection, e: Eintrag) -> int:
    angelegt = e.angelegt_am or datetime.now().replace(microsecond=0)
    cur = con.execute(
        f"INSERT INTO eintraege (angelegt_am, {', '.join(_FELDER)}) VALUES (?{', ?' * len(_FELDER)})",
        (angelegt.isoformat(), *_werte(e)))
    con.commit()
    return cur.lastrowid


def aendern(con: sqlite3.Connection, e: Eintrag) -> None:
    con.execute(f"UPDATE eintraege SET {', '.join(f + ' = ?' for f in _FELDER)} WHERE id = ?",
                (*_werte(e), e.id))
    con.commit()


def loeschen(con: sqlite3.Connection, id: int) -> None:
    con.execute("DELETE FROM eintraege WHERE id = ?", (id,))
    con.commit()


def _eintrag(z: sqlite3.Row | tuple) -> Eintrag:
    (id_, angelegt, start, ende, anlass, ergebnis, gruppe, km_g, km_t, preis_g, preis_t,
     eigen, vergleich) = z
    return Eintrag(datetime.fromisoformat(start), datetime.fromisoformat(ende), anlass, ergebnis,
                   gruppe, km_g, preis_g, bool(eigen), km_t, preis_t,
                   None if vergleich is None else json.loads(vergleich),
                   id_, datetime.fromisoformat(angelegt))


_SPALTEN = ("SELECT id, angelegt_am, start, ende, anlass, ergebnis, gruppe, km_geplant, km_tatsaechlich, "
            "preis_geplant, preis_tatsaechlich, eigenauto_gefahren, vergleich FROM eintraege")


def alle(con: sqlite3.Connection) -> list[Eintrag]:
    zeilen = con.execute(f"{_SPALTEN} ORDER BY start DESC, id DESC").fetchall()
    return [_eintrag(z) for z in zeilen]


def holen(con: sqlite3.Connection, id: int) -> Eintrag | None:
    z = con.execute(f"{_SPALTEN} WHERE id = ?", (id,)).fetchone()
    return None if z is None else _eintrag(z)


def rechnung_nachtragen(con: sqlite3.Connection, id: int, preis: float, km: float | None) -> None:
    """Nur Preis und ggf. km – gleichzeitige Änderungen an anderen Feldern (App) bleiben erhalten."""
    con.execute("UPDATE eintraege SET preis_tatsaechlich = ?, km_tatsaechlich = COALESCE(?, km_tatsaechlich) "
                "WHERE id = ?", (preis, km, id))
    con.commit()


def doppelt(con: sqlite3.Connection, e: Eintrag) -> int | None:
    """id einer schon gespeicherten Fahrt mit gleicher Zeit, gleichem Ergebnis und Anlass."""
    z = con.execute("SELECT id FROM eintraege WHERE start = ? AND ende = ? AND ergebnis = ? AND anlass = ? "
                    "ORDER BY id LIMIT 1", (e.start.isoformat(), e.ende.isoformat(), e.ergebnis, e.anlass)).fetchone()
    return None if z is None else z[0]
