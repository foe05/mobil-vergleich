"""HTTP-Schicht der Schnittstelle: Anmeldung, Grenzen, Wege, Protokoll."""
import json
import logging
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from schnittstelle import logik
from schnittstelle.server import baue_server

SCHLUESSEL = "k" * 40
TARIFE = Path(__file__).parent.parent / "tarife"
REISE = {"start": "2026-11-14T10:00", "ende": "2026-11-15T16:00", "km": 100,
         "angebote": [{"anbieter": "sixt", "preis": 123.45}]}


def _starten(tmp_path, schluessel):
    srv = baue_server(("127.0.0.1", 0), schluessel, TARIFE, tmp_path / "m.db")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture
def url(tmp_path, monkeypatch):
    monkeypatch.setattr(logik.telemetrie, "senden", lambda *a: None)
    srv, u = _starten(tmp_path, SCHLUESSEL)
    yield u
    srv.shutdown()
    srv.server_close()


def ruf(url, pfad, methode="GET", koerper=None, schluessel=SCHLUESSEL, roh=None):
    daten = roh if roh is not None else (None if koerper is None else json.dumps(koerper).encode())
    kopf = {"Content-Type": "application/json"}
    if schluessel:
        kopf["Authorization"] = f"Bearer {schluessel}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url + pfad, data=daten, method=methode, headers=kopf)) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_lebt_ohne_schluessel(url):
    assert ruf(url, "/lebt", schluessel=None) == (200, {"ok": True})


def test_ohne_kopf_401(url):
    assert ruf(url, "/fahrten", schluessel=None)[0] == 401


def test_falscher_schluessel_401(url):
    assert ruf(url, "/fahrten", schluessel="x" * 40)[0] == 401


def test_zu_gross_413(url):
    assert ruf(url, "/vergleich", "POST", roh=b"{" + b" " * (64 * 1024 + 1) + b"}")[0] == 413


def test_kaputtes_json_400(url):
    assert ruf(url, "/vergleich", "POST", roh=b"{nein")[0] == 400


def test_unbekannt_404(url):
    assert ruf(url, "/geheim")[0] == 404
    assert ruf(url, "/fahrten/abc", "PATCH", {"preis_tatsaechlich": 1})[0] == 404


def test_methode_405(url):
    assert ruf(url, "/vergleich")[0] == 405
    assert ruf(url, "/fahrten", "DELETE")[0] == 405


def test_ohne_eingerichteten_schluessel_503(tmp_path):
    srv, u = _starten(tmp_path, "kurz")
    try:
        assert ruf(u, "/lebt", schluessel=None)[0] == 200
        status, a = ruf(u, "/fahrten", schluessel="kurz")
        assert status == 503 and "MOBIL_API_KEY" in a["fehler"]
    finally:
        srv.shutdown(); srv.server_close()


def test_ende_zu_ende(url):
    status, a = ruf(url, "/vergleich", "POST", REISE)
    assert status == 200 and any(r["anbieter"] == "Sixt" for r in a["rangliste"])
    status, f = ruf(url, "/fahrten", "POST", REISE | {"wahl": "Sixt · Angebot", "eigenes_auto": True, "anlass": "Oma"})
    assert status == 201
    i = f["fahrt"]["id"]
    assert ruf(url, "/fahrten?offen=0&anzahl=5")[1]["fahrten"][0]["id"] == i
    status, r = ruf(url, f"/fahrten/{i}", "PATCH", {"preis_tatsaechlich": 130})
    assert status == 200 and r["fahrt"]["preis_tatsaechlich"] == 130
    assert ruf(url, "/auswertung?zeitraum=jahr&datum=2026-11-14")[0] == 200


def test_log_ohne_koerper_und_schluessel(url, caplog):
    with caplog.at_level(logging.INFO):
        ruf(url, "/vergleich?x=geheim", "POST", REISE)
    text = caplog.text
    assert "POST /vergleich 200" in text
    assert "123.45" not in text and SCHLUESSEL not in text and "geheim" not in text
