"""Telemetrie an tool-log: Inhalt der Einträge, keine Doppelungen, Ausfälle stören nicht."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading

import pytest

from engine import Eintrag, Ergebnis, Szenario
import telemetrie

SZ = Szenario(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), km=100)
ERG = [Ergebnis("scouter Kassel", "Klasse M (Kombi)", "Carsharing", 92.49, {"Zeit": 58.7}),
       Ergebnis("Nachbar", "freies Angebot", "Sonstiges", 120.0)]


def test_vergleich_daten():
    d = telemetrie.vergleich_daten(SZ, "Oma (1 Nacht)", {"sixt": 150.0}, ERG)
    assert d["start"] == "2026-10-10T10:00:00" and d["ende"] == "2026-10-11T16:00:00"
    assert (d["stunden"], d["km"], d["hund"], d["vorlage"]) == (30.0, 100, True, "Oma (1 Nacht)")
    assert d["angebote"] == {"sixt": 150.0}
    assert d["guenstigste"] == {"anbieter": "scouter Kassel", "option": "Klasse M (Kombi)", "gesamt": 92.49}
    assert d["rangliste"][1] == {"anbieter": "Nachbar", "option": "freies Angebot", "gruppe": "Sonstiges",
                                 "gesamt": 120.0}
    json.dumps(d)   # muss JSON-tauglich sein


def test_entscheidung_daten():
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter Kassel · Klasse M (Kombi)",
                "Carsharing", 100, 92.49, True)
    assert telemetrie.entscheidung_daten(e) == {
        "start": "2026-10-10T10:00:00", "ende": "2026-10-11T16:00:00", "anlass": "Oma",
        "ergebnis": "scouter Kassel · Klasse M (Kombi)", "gruppe": "Carsharing", "preis_geplant": 92.49,
        "km_geplant": 100, "eigenauto_gefahren": True}


def test_nur_einmal_pro_sitzung():
    sitzung = {}
    assert telemetrie.neu_in_sitzung(sitzung, "vergleich", {"km": 100})
    assert not telemetrie.neu_in_sitzung(sitzung, "vergleich", {"km": 100})
    assert telemetrie.neu_in_sitzung(sitzung, "vergleich", {"km": 120})
    assert telemetrie.neu_in_sitzung(sitzung, "entscheidung", {"km": 100})   # andere Ereignisart zählt extra


def test_ohne_api_key_wird_nichts_gesendet(monkeypatch):
    monkeypatch.delenv("TOOLLOG_API_KEY", raising=False)
    assert telemetrie.senden("vergleich", {}) is None


@pytest.fixture
def empfaenger():
    erhalten = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            laenge = int(self.headers["Content-Length"])
            erhalten.append((self.headers["X-Api-Key"], json.loads(self.rfile.read(laenge))))
            self.send_response(201)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/api/log", erhalten
    server.shutdown()


def test_senden_an_tool_log(monkeypatch, empfaenger):
    url, erhalten = empfaenger
    monkeypatch.setenv("TOOLLOG_API_KEY", "geheim")
    monkeypatch.setenv("TOOLLOG_API_URL", url)
    monkeypatch.setenv("TOOLLOG_INSTANZ", "mobil.example.org")
    telemetrie.senden("vergleich", {"km": 100}).join(5)
    schluessel, nachricht = erhalten[0]
    assert schluessel == "geheim"
    assert nachricht == {"tool": "mobil-vergleich", "tool_version": telemetrie.VERSION,
                         "instance": "mobil.example.org", "event": "vergleich", "payload": {"km": 100}}


def test_ausfall_stoert_nicht(monkeypatch, caplog):
    monkeypatch.setenv("TOOLLOG_API_KEY", "geheim")
    monkeypatch.setenv("TOOLLOG_API_URL", "http://127.0.0.1:9/api/log")   # dort lauscht niemand
    faden = telemetrie.senden("vergleich", {"km": 100})
    faden.join(5)
    assert not faden.is_alive()
    assert "tool-log" in caplog.text
