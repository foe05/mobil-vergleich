"""Tests für Eintrag, Profil und Referenzprofile (eigenes Auto)."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from engine import Eintrag, Profil, NICHT_GEFAHREN, lade_tarife


def test_profil_summen():
    p = Profil("x", "X", "q", "2026-10-06", {"a": 3000, "b": 650}, {"e": 0.08, "r": 0.02})
    assert p.fix == 3650 and p.variabel == pytest.approx(0.10)


def test_eintrag_tatsaechlich_vor_geplant():
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter", "Carsharing",
                100, 92.49, True, km_tatsaechlich=110, preis_tatsaechlich=100)
    assert (e.km, e.preis, e.gefahren) == (110, 100, True)


def test_rechnung_offen():
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter", "Carsharing", 100, 92.49, True)
    assert e.rechnung_offen(datetime(2026, 10, 12)) and not e.rechnung_offen(datetime(2026, 10, 11, 12))
    assert not replace(e, ergebnis=NICHT_GEFAHREN).rechnung_offen(datetime(2026, 10, 12))


def test_profile_laden_mit_fehlerhaftem(tmp_path):
    (tmp_path / "eigenes_auto.yaml").write_text(
        "typ: eigenauto\nprofile:\n"
        "  - {id: ok, name: OK, quelle: q, stand: '2026-10-06', fix_pro_jahr: {a: 1}, variabel_pro_km: {e: 0.1}}\n"
        "  - {id: kaputt, name: Kaputt}\n", encoding="utf-8")
    t = lade_tarife(tmp_path)
    assert [p.id for p in t["eigenauto"]] == ["ok"] and "Kaputt" in t["hinweise"][0]


def test_echte_profile_laden():
    t = lade_tarife(Path(__file__).parent.parent / "tarife")
    assert {p.id for p in t["eigenauto"]} == {"e-kombi-leasing", "e-kombi-gebraucht", "verbrenner-kombi-gebraucht"}
    assert all(p.fix > 0 and p.variabel > 0 for p in t["eigenauto"])
