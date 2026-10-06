"""Tests gegen die offiziellen Preisbeispiele der Anbieter (Stand 2026-10-06)."""
from datetime import datetime
from pathlib import Path

import pytest

from engine import Szenario, MietAngebot, BahnAngebot, lade_tarife, berechne_carsharing, vergleiche
from engine.berechnung import zeitkosten

TARIFE = lade_tarife(Path(__file__).parent.parent / "tarife")
SCOUTER = next(t for t in TARIFE["carsharing"] if t["anbieter"] == "scouter")
FLINKSTER = next(t for t in TARIFE["carsharing"] if t["anbieter"] == "flinkster")


def klasse(tarif, kid):
    return next(k for k in tarif["klassen"] if k["id"] == kid)


def test_scouter_preisbeispiel_kombi():
    # scouter.de/kassel: 100 km, 24 h, Kombi, mit 500-km-Paket = 68,79 €
    sz = Szenario(datetime(2026, 10, 10, 9), datetime(2026, 10, 11, 9), km=100)
    assert berechne_carsharing(SCOUTER, klasse(SCOUTER, "M"), sz).gesamt == pytest.approx(68.79)


def test_scouter_preisbeispiel_kleinwagen():
    # scouter.de/kassel: 10 km, 2,5 h, Spezial (1,95 €/h) = 9,87 €
    spezial = {"name": "Spezial", "stundenpreis": 1.95, "tagespreis": 25, "wochenpreis": None, "km_preis": 0.42}
    sz = Szenario(datetime(2026, 10, 10, 9), datetime(2026, 10, 10, 11, 30), km=10)
    assert berechne_carsharing(SCOUTER, spezial, sz).gesamt == pytest.approx(9.87, abs=0.01)


def test_flinkster_wochenendtarif():
    # Fr 14:00 – Mo 06:00, 300 km: Deckel 139 € + 250 km × 0,36 + 1,90
    sz = Szenario(datetime(2026, 10, 9, 14), datetime(2026, 10, 12, 6), km=300)
    e = berechne_carsharing(FLINKSTER, klasse(FLINKSTER, "golf_variant"), sz)
    assert e.gesamt == pytest.approx(1.90 + 139 + 250 * 0.36)
    assert "Wochenend" in e.hinweise[0]


def test_flinkster_kurz_ohne_pauschale():
    # Sa 13–17 Uhr, 30 km: Stundenpreis liegt unter dem Sa/So-Deckel -> keine Freikilometer
    sz = Szenario(datetime(2026, 10, 10, 13), datetime(2026, 10, 10, 17), km=30)
    e = berechne_carsharing(FLINKSTER, klasse(FLINKSTER, "golf_variant"), sz)
    assert e.gesamt == pytest.approx(1.90 + 4 * 6.90 + 30 * 0.36)


def test_flinkster_erste_stunde_voll():
    sz = Szenario(datetime(2026, 10, 7, 10), datetime(2026, 10, 7, 10, 20), km=5)
    e = berechne_carsharing(FLINKSTER, klasse(FLINKSTER, "golf_variant"), sz)
    assert e.posten["Zeit"] == pytest.approx(6.90)


def test_zeitkosten_wochendeckel():
    # 10 Tage Klasse M: 1 Woche (150) + 3 Tage (105)
    assert zeitkosten(240, 3.95, 35, 150) == pytest.approx(255)
    # 6 Tage: 6 × 35 = 210 > Wochenpreis 150 -> 150
    assert zeitkosten(144, 3.95, 35, 150) == pytest.approx(150)


def test_mietwagen_mit_sprit_und_mehrkm():
    sz = Szenario(datetime(2026, 10, 9, 14), datetime(2026, 10, 12, 18), km=800, spritpreis=1.80)
    a = MietAngebot("sixt", "Sixt", preis_gesamt=180, frei_km=600, mehr_km_preis=0.25, verbrauch_l_100km=6.5)
    e = vergleiche({"carsharing": []}, sz, [a], None)[0]
    assert e.gesamt == pytest.approx(180 + 200 * 0.25 + 800 * 0.065 * 1.80)


def test_vergleich_sortiert_und_filtert_hund():
    sz = Szenario(datetime(2026, 10, 10, 9), datetime(2026, 10, 11, 9), km=100, hund=True)
    miet = [MietAngebot("x", "Kein-Hund-Vermieter", 10, haustiere="nein")]
    e = vergleiche(TARIFE, sz, miet, BahnAngebot(preis_gesamt=90))
    assert all(x.anbieter != "Kein-Hund-Vermieter" for x in e)
    assert [x.gesamt for x in e] == sorted(x.gesamt for x in e)
