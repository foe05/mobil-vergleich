"""Tests für Eintrag, Profil und Referenzprofile (eigenes Auto)."""
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from engine import Eintrag, Profil, NICHT_GEFAHREN, lade_tarife
from engine.eigenauto import zeitraum, zeitraeume, zeitraumkosten


@pytest.fixture
def profil():
    return Profil("x", "X", "q", "2026-10-06", {"fix": 3650}, {"km": 0.10})


@pytest.fixture
def vier_faelle():
    def e(tag, ergebnis, gruppe, km, preis, auto):
        return Eintrag(datetime(2026, 10, tag, 10), datetime(2026, 10, tag, 18), "Test", ergebnis, gruppe, km, preis, auto)
    return [
        e(1, "scouter", "Carsharing", 100, 92.49, True),
        e(5, NICHT_GEFAHREN, "keine", 200, 0, True),
        e(10, "Bahn", "Bahn", 300, 120, False),
        e(15, NICHT_GEFAHREN, "keine", 50, 0, False),
    ]


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


def test_quartal_vier_faelle(vier_faelle, profil):
    zr = zeitraum("quartal", date(2026, 10, 10), heute=date(2027, 1, 15))
    assert (zr.von, zr.bis, zr.tage, zr.label) == (date(2026, 10, 1), date(2026, 12, 31), 92, "Q4 2026")
    k = zeitraumkosten(vier_faelle, profil, zr)
    assert (k.ist, k.mit_profil, k.differenz) == (212.49, 1070.0, 857.51)


def test_laufender_zeitraum_bis_heute(vier_faelle, profil):
    zr = zeitraum("quartal", date(2026, 10, 10), heute=date(2026, 11, 15))
    assert zr.tage == 46 and zeitraumkosten(vier_faelle, profil, zr).mit_profil == 460.0 + 30 + 120


def test_eintrag_ohne_km_zaehlt_preis(profil):
    taxi = Eintrag(datetime(2026, 10, 3), datetime(2026, 10, 3), "Taxi", "Taxi", "Sonstiges", 0, 25, True)
    k = zeitraumkosten([taxi], profil, zeitraum("monat", date(2026, 10, 3), heute=date(2026, 11, 1)))
    assert k.ist == 25 and k.mit_profil == 310.0


def test_zeitraeume_liste(vier_faelle):
    assert [z.label for z in zeitraeume("monat", vier_faelle, date(2027, 1, 15))] == ["Oktober 2026"]
    assert zeitraeume("gesamt", vier_faelle, date(2027, 1, 15))[0].von == date(2026, 10, 1)


def test_labels_jahr_gesamt_und_reihenfolge(vier_faelle):
    assert zeitraum("jahr", date(2026, 5, 1), heute=date(2026, 10, 6)).label == "2026"
    assert zeitraum("gesamt", date(2026, 10, 6), heute=date(2026, 10, 6), erster=date(2026, 10, 1)).label == "Gesamt"
    spaeter = Eintrag(datetime(2026, 12, 2), datetime(2026, 12, 2), "x", "Bahn", "Bahn", 10, 5, False)
    assert [z.label for z in zeitraeume("monat", vier_faelle + [spaeter], date(2027, 1, 15))] == ["Dezember 2026", "Oktober 2026"]
