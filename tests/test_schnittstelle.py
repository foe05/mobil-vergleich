"""Schnittstellen-Logik ohne HTTP: dict rein, (Status, dict) raus."""
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from engine import Instanz, Szenario, lade_tarife, vergleiche, zeitraum, zeitraumkosten
from schnittstelle import logik
from speicher.fahrten import alle, holen, oeffnen

T = lade_tarife(Path(__file__).parent.parent / "tarife")
I = Instanz()
REISE = {"start": "2026-11-14T10:00", "ende": "2026-11-15T16:00", "km": 100}


@pytest.fixture
def con(tmp_path):
    c = oeffnen(tmp_path / "m.db")
    yield c
    c.close()


@pytest.fixture(autouse=True)
def kein_toollog(monkeypatch):
    gesendet = []
    monkeypatch.setattr(logik.telemetrie, "senden", lambda ev, d: gesendet.append((ev, d)))
    return gesendet


def test_vergleich_gleich_engine():
    status, a = logik.vergleich(dict(REISE), T, I)
    erwartet = vergleiche(T, Szenario(datetime(2026, 11, 14, 10), datetime(2026, 11, 15, 16), 100), [], None)
    assert status == 200
    assert [r["gesamt"] for r in a["rangliste"]] == [e.gesamt for e in erwartet]
    assert a["rangliste"][0]["wahl"] == "scouter Kassel · Klasse M (Kombi)"
    assert set(a["suchlinks"]) == {"sixt", "europcar", "getaround", "bahn"}
    assert "zen_pu_time=2026-11-14T10%3A00" in a["suchlinks"]["sixt"]
    assert a["reise"]["hund"] is True and a["reise"]["spritpreis"] == 1.75 and a["reise"]["angebote"] == []


def test_vergleich_mit_sixt_angebot():
    status, a = logik.vergleich(REISE | {"angebote": [{"anbieter": "sixt", "preis": 50}]}, T, I)
    assert status == 200
    sixt = next(r for r in a["rangliste"] if r["anbieter"] == "Sixt")
    assert sixt["wahl"] == "Sixt · Angebot" and sixt["gesamt"] > 50   # plus Sprit


def test_vergleich_bahn_und_frei():
    _, a = logik.vergleich(REISE | {"angebote": [{"anbieter": "bahn", "preis": 80, "vor_ort": 10},
                                                 {"anbieter": "frei", "preis": 30, "beschreibung": "Nachbar"}]}, T, I)
    namen = {r["anbieter"]: r["gesamt"] for r in a["rangliste"]}
    assert namen["Bahn"] == 90 and namen["Nachbar"] == 30


@pytest.mark.parametrize("aenderung, wort", [
    ({"ende": "2026-11-14T09:00"}, "Rückgabe"),
    ({"km": 100_001}, "km"),
    ({"km": "viel"}, "km"),
    ({"start": "14.11.2026"}, "start"),
    ({"farbe": "rot"}, "farbe"),
    ({"angebote": [{"anbieter": "hertz", "preis": 1}]}, "hertz"),
    ({"angebote": [{"anbieter": "sixt", "preis": 1}, {"anbieter": "sixt", "preis": 2}]}, "doppelt"),
    ({"angebote": [{"anbieter": "frei", "preis": 1, "beschreibung": "x" * 201}]}, "beschreibung"),
    ({"angebote": [{"anbieter": "sixt", "preis": 100_001}]}, "preis"),
    ({"angebote": [{"anbieter": "sixt", "preis": 1, "vor_ort": 3}]}, "vor_ort"),
    ({"hund": "ja"}, "hund"),
])
def test_ungueltige_reise_400(aenderung, wort):
    status, a = logik.vergleich(REISE | aenderung, T, I)
    assert status == 400 and wort in a["fehler"]


def test_koerper_kein_objekt_400():
    assert logik.vergleich([1], T, I)[0] == 400


def test_fahrt_anlegen_201_mit_schnappschuss(con, kein_toollog):
    status, a = logik.fahrt_anlegen(REISE | {"wahl": "Flinkster · Kompakt (VW Golf Variant)", "eigenes_auto": True,
                                             "anlass": "Oma"}, T, I, con)
    assert status == 201
    f = a["fahrt"]
    assert f["preis_geplant"] == 148.3 and f["gruppe"] == "Carsharing" and f["anlass"] == "Oma"
    gespeichert = holen(con, f["id"])
    assert gespeichert.vergleich["rangliste"][0]["gesamt"] == 92.49
    assert gespeichert.eigenauto_gefahren is True
    assert kein_toollog[0][0] == "entscheidung"


def test_fahrt_wahl_fremd_400(con):
    status, a = logik.fahrt_anlegen(REISE | {"wahl": "Getaround · Angebot", "eigenes_auto": False, "anlass": ""},
                                    T, I, con)
    assert status == 400 and "Rangliste" in a["fehler"] and alle(con) == []


def test_fahrt_nicht_gefahren(con):
    status, a = logik.fahrt_anlegen(REISE | {"wahl": "nicht gefahren", "eigenes_auto": False, "anlass": ""}, T, I, con)
    assert status == 201 and a["fahrt"]["gruppe"] == "keine" and a["fahrt"]["preis_geplant"] == 0


def test_fahrt_pflichtfelder_400(con):
    assert logik.fahrt_anlegen(REISE | {"wahl": "nicht gefahren"}, T, I, con)[0] == 400


def test_fahrt_doppelt_409_mit_id(con):
    k = REISE | {"wahl": "scouter Kassel · Klasse M (Kombi)", "eigenes_auto": True, "anlass": "Oma"}
    _, a = logik.fahrt_anlegen(dict(k), T, I, con)
    status, b = logik.fahrt_anlegen(dict(k), T, I, con)
    assert status == 409 and b["id"] == a["fahrt"]["id"] and len(alle(con)) == 1


def _anlegen(con, start, wahl="scouter Kassel · Klasse M (Kombi)", anlass="Oma"):
    ende = (datetime.fromisoformat(start) + timedelta(hours=5)).isoformat(timespec="minutes")
    return logik.fahrt_anlegen({"start": start, "ende": ende, "km": 50, "wahl": wahl, "eigenes_auto": True,
                                "anlass": anlass}, T, I, con)[1]["fahrt"]["id"]


def test_fahrten_offen_filter(con):
    alt = _anlegen(con, "2026-10-01T10:00")
    _anlegen(con, "2026-12-01T10:00", anlass="Zukunft")
    _anlegen(con, "2026-10-02T10:00", wahl="nicht gefahren", anlass="aus")
    jetzt = datetime(2026, 11, 9, 12)
    status, a = logik.fahrten({"offen": "1"}, con, jetzt)
    assert status == 200 and [f["id"] for f in a["fahrten"]] == [alt]
    assert a["fahrten"][0]["rechnung_offen"] is True
    assert len(logik.fahrten({}, con, jetzt)[1]["fahrten"]) == 3
    assert len(logik.fahrten({"anzahl": "1"}, con, jetzt)[1]["fahrten"]) == 1
    assert "vergleich" not in a["fahrten"][0]


@pytest.mark.parametrize("q", [{"anzahl": "0"}, {"anzahl": "101"}, {"anzahl": "x"}, {"offen": "vielleicht"}])
def test_fahrten_query_400(con, q):
    assert logik.fahrten(q, con, datetime.now())[0] == 400


def test_rechnung_200(con):
    i = _anlegen(con, "2026-10-01T10:00")
    status, a = logik.rechnung(str(i), {"preis_tatsaechlich": 79.1, "km_tatsaechlich": 48}, con)
    assert status == 200 and a["fahrt"]["preis_tatsaechlich"] == 79.1 and a["fahrt"]["km_tatsaechlich"] == 48


def test_rechnung_unbekannt_404(con):
    assert logik.rechnung("99", {"preis_tatsaechlich": 1}, con)[0] == 404
    assert logik.rechnung("abc", {"preis_tatsaechlich": 1}, con)[0] == 404


def test_rechnung_nicht_gefahren_400(con):
    i = _anlegen(con, "2026-10-01T10:00", wahl="nicht gefahren")
    assert logik.rechnung(str(i), {"preis_tatsaechlich": 1}, con)[0] == 400


@pytest.mark.parametrize("k", [{"preis_tatsaechlich": 1, "anlass": "x"}, {}, {"preis_tatsaechlich": -1},
                               {"preis_tatsaechlich": 1, "km_tatsaechlich": 100_001}])
def test_rechnung_ungueltig_400(con, k):
    i = _anlegen(con, "2026-10-01T10:00")
    assert logik.rechnung(str(i), k, con)[0] == 400


def test_auswertung_gleich_zeitraumkosten(con):
    for t in ("2026-10-01T10:00", "2026-10-08T10:00", "2026-10-15T10:00"):
        _anlegen(con, t, anlass=t)
    heute = date(2026, 11, 9)
    status, a = logik.auswertung({"zeitraum": "quartal"}, T, con, heute)
    assert status == 200 and a["zeitraum"]["label"] == "Q4 2026"
    zr = zeitraum("quartal", heute, heute)
    erwartet = sorted((zeitraumkosten(alle(con), p, zr).differenz for p in T["eigenauto"]))
    assert [p["differenz"] for p in a["profile"]] == erwartet
    assert all(p["break_even"] for p in a["profile"])
    assert a["offene_rechnungen"] == 3
    status, b = logik.auswertung({"zeitraum": "monat", "datum": "2026-10-05"}, T, con, heute)
    assert b["zeitraum"]["label"] == "Oktober 2026"


def test_auswertung_leer(con):
    status, a = logik.auswertung({}, T, con, date(2026, 11, 9))
    assert status == 200 and a["profile"] == [] and a["hinweise"]


@pytest.mark.parametrize("q", [{"zeitraum": "woche"}, {"datum": "gestern"}])
def test_auswertung_ungueltig_400(con, q):
    assert logik.auswertung(q, T, con, date(2026, 11, 9))[0] == 400
