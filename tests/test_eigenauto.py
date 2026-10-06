"""Tests für Eintrag, Profil und Referenzprofile (eigenes Auto)."""
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from engine import Eintrag, Profil, NICHT_GEFAHREN, lade_tarife
from engine.eigenauto import zeitraum, zeitraeume, zeitraumkosten, break_even, verlauf


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


def test_geplante_fahrt_zaehlt_im_eigenen_zeitraum(vier_faelle, profil):
    geplant = Eintrag(datetime(2026, 11, 20), datetime(2026, 11, 20), "Plan", "Bahn", "Bahn", 10, 40, False)
    zr = zeitraum("quartal", date(2026, 10, 10), heute=date(2026, 11, 15))
    k = zeitraumkosten(vier_faelle + [geplant], profil, zr)
    assert zr.tage == 46 and k.ist == 252.49 and k.mit_profil == 460.0 + 30 + 120 + 40


def test_rein_zukuenftiger_zeitraum(profil):
    e = Eintrag(datetime(2027, 2, 10), datetime(2027, 2, 10), "Plan", "Bahn", "Bahn", 10, 40, False)
    heute = date(2026, 11, 15)
    zr = zeitraeume("monat", [e], heute)[0]
    assert zr.label == "Februar 2027" and zr.tage == 0
    k = zeitraumkosten([e], profil, zr)
    assert (k.ist, k.mit_profil) == (40, 40)


def drei_oma_ab(d):
    return [Eintrag(datetime(d.year, d.month, d.day + i, 10), datetime(d.year, d.month, d.day + i, 18),
                    "Oma", "scouter", "Carsharing", 100, 50, True) for i in range(3)]


@pytest.fixture
def basis():
    drei = drei_oma_ab(date(2027, 9, 10))
    alt = Eintrag(datetime(2026, 6, 1, 10), datetime(2026, 6, 1, 18), "Alt", "scouter", "Carsharing", 100, 50, True)
    return drei + [alt]


def test_break_even_schwelle(basis, profil):
    b = break_even(basis, profil, date(2027, 10, 1))
    assert (b.status, b.schwelle_km, b.km_jahr, b.weitere_fahrten, b.anlass, b.hochgerechnet) == \
           ("schwelle", 9125, 300, 89, "Oma", False)


def test_break_even_nie(basis):
    assert break_even(basis, Profil("x", "X", "q", "s", {"a": 3650}, {"e": 0.6}), date(2027, 10, 1)).status == "nie"


def test_break_even_bereits(basis):
    assert break_even(basis, Profil("x", "X", "q", "s", {"a": 10}, {"e": 0.1}), date(2027, 10, 1)).status == "bereits"


def test_break_even_zu_wenig_daten(basis, profil):
    assert break_even(basis[:2], profil, date(2027, 10, 1)).status == "zu_wenig_daten"


def test_break_even_keine_km(profil):
    nullkm = [replace(e, km_geplant=0) for e in drei_oma_ab(date(2027, 9, 10))]
    assert break_even(nullkm, profil, date(2027, 10, 1)).status == "zu_wenig_daten"


def test_break_even_hochrechnung(profil):
    b = break_even(drei_oma_ab(date(2027, 1, 1)), profil, date(2027, 1, 31))
    assert b.hochgerechnet and b.km_jahr == pytest.approx(3650)


def test_break_even_mindestspanne(profil):
    assert break_even(drei_oma_ab(date(2027, 1, 25)), profil, date(2027, 1, 31)).km_jahr == pytest.approx(3650)


def test_break_even_ignoriert_zukunft(basis, profil):
    zukunft = replace(basis[0], start=datetime(2027, 12, 1), ende=datetime(2027, 12, 2))
    assert break_even(basis + [zukunft], profil, date(2027, 10, 1)).km_jahr == 300


def test_verlauf_endwerte(vier_faelle, profil):
    zeilen = verlauf(vier_faelle, [profil], date(2026, 12, 31))
    ende = {z["reihe"]: z["kumuliert"] for z in zeilen if z["datum"] == date(2026, 12, 31)}
    assert ende["Heute"] == 212.49 and ende[profil.name] == pytest.approx(920 + 30 + 120)


def test_verlauf_ohne_zukunft(vier_faelle, profil):
    zeilen = verlauf(vier_faelle, [profil], date(2026, 10, 7))
    assert max(z["datum"] for z in zeilen) == date(2026, 10, 7) and verlauf([], [profil], date(2026, 10, 7)) == []
