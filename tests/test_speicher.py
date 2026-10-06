"""Tests für den SQLite-Speicher der Einträge."""
from dataclasses import replace
from datetime import datetime

from engine import Eintrag
from speicher.fahrten import oeffnen, anlegen, aendern, loeschen, alle

BEISPIEL = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 10, 18), "Einkauf",
                   "scouter Kassel · Klasse M", "Carsharing", 40, 35.0, False)


def test_schema_idempotent(tmp_path):
    p = tmp_path / "unter" / "mobil.db"           # Verzeichnis existiert noch nicht
    oeffnen(p).close(); con = oeffnen(p)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1


def test_rundreise_mit_vergleich(tmp_path):
    con = oeffnen(tmp_path / "m.db")
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter", "Carsharing",
                100, 92.49, True, vergleich={"rangliste": [{"anbieter": "scouter", "gesamt": 92.49}]})
    e.id = anlegen(con, e)
    assert alle(con) == [replace(e, angelegt_am=alle(con)[0].angelegt_am)]


def test_nachtragen_und_loeschen(tmp_path):
    con = oeffnen(tmp_path / "m.db")
    e = replace(BEISPIEL); e.id = anlegen(con, e)
    aendern(con, replace(e, preis_tatsaechlich=101.5, km_tatsaechlich=104))
    assert alle(con)[0].preis == 101.5
    loeschen(con, e.id); assert alle(con) == []


def test_sortierung(tmp_path):
    con = oeffnen(tmp_path / "m.db")
    for tag in (3, 20, 11):
        anlegen(con, replace(BEISPIEL, start=datetime(2026, 10, tag), ende=datetime(2026, 10, tag, 18)))
    assert [e.start.day for e in alle(con)] == [20, 11, 3]
