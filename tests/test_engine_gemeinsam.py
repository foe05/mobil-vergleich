"""Was App und Schnittstelle teilen: Suchlinks, Schnappschuss, Texte, Grenzen."""
from datetime import date, datetime
from pathlib import Path

from engine import BreakEven, Profil, Szenario, lade_tarife, vergleiche
from engine.grenzen import EURO_MAX, KM_MAX, TEXT_MAX
from engine.schnappschuss import schnappschuss
from engine.suchlinks import suchlink
from engine.texte import break_even_satz, euro, zahl

T = lade_tarife(Path(__file__).parent.parent / "tarife")
START, ENDE = datetime(2026, 11, 14, 10), datetime(2026, 11, 15, 16)


def test_grenzen():
    assert (EURO_MAX, KM_MAX, TEXT_MAX) == (100_000.0, 100_000, 200)


def test_suchlink_sixt():
    sixt = next(m for m in T["angebote"]["mietwagen"] if m["id"] == "sixt")
    assert "zen_pu_time=2026-11-14T10%3A00" in suchlink(sixt, START, ENDE)


def test_schnappschuss_gleich_rangliste():
    sz = Szenario(START, ENDE, 100)
    erg = vergleiche(T, sz, [], None)
    s = schnappschuss(sz, erg, T)
    assert s["rangliste"][0]["gesamt"] == erg[0].gesamt
    assert s["szenario"]["km_paket_nutzen"] is True and s["szenario"]["start"] == START.isoformat()
    assert set(s["tarifstand"]) == {t["name"] for t in T["carsharing"]}


def test_texte():
    assert euro(1234.5) == "1.234,50 €"
    assert zahl(1234.56) == "1.234,6"
    p = Profil("x", "Kleinwagen", "q", "2026", {"a": 1.0}, {"b": 0.1})
    assert break_even_satz(p, BreakEven("zu_wenig_daten")).startswith("Für eine Schwelle")


def test_aus_link_gueltig():
    from datetime import time
    from engine.suchlinks import aus_link
    w = aus_link({"start": "2026-11-14T10:00", "ende": "2026-11-15T16:30", "km": "333", "hund": "0", "anlass": "Oma"})
    assert w == {"start_d": date(2026, 11, 14), "start_t": time(10), "ende_d": date(2026, 11, 15),
                 "ende_t": time(16, 30), "km": 333, "hund": False, "anlass": "Oma"}
    assert "hund" not in aus_link({"start": "2026-11-14T10:00", "ende": "2026-11-15T16:30", "km": "5"})


import pytest  # noqa: E402


@pytest.mark.parametrize("q", [
    {"start": "2026-11-14T10:00", "ende": "2026-11-14T09:00", "km": "5"},
    {"start": "2026-11-14T10:00", "ende": "2026-11-15T09:00", "km": "abc"},
    {"start": "2026-11-14T10:00", "km": "5"},
    {"start": "2026-11-14T10:00", "ende": "2026-11-15T09:00", "km": "100001"},
    {"start": "2026-11-14T10:00", "ende": "2026-11-15T09:00", "km": "5", "hund": "vielleicht"},
    {},
])
def test_aus_link_unsinn_none(q):
    from engine.suchlinks import aus_link
    assert aus_link(q) is None
