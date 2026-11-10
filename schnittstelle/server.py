"""HTTP-Schicht der Schnittstelle: Anmeldung, Größengrenze, Wege, JSON. Die Logik steht in logik.py.

Sicherheit: nur 127.0.0.1 (Port-Bindung in docker-compose.yml), jeder Aufruf außer /lebt braucht
`Authorization: Bearer <MOBIL_API_KEY>`. Protokolliert werden nur Methode, Pfad, Status und Dauer.
"""
from __future__ import annotations

import hmac
import json
import logging
import re
import sqlite3
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from engine import lade_instanz, lade_tarife
from schnittstelle import logik
from speicher.fahrten import oeffnen

KOERPER_MAX = 64 * 1024
SCHLUESSEL_MIN = 32
log = logging.getLogger("mobil-api")
_FAHRT = re.compile(r"^/fahrten/([^/]+)$")
WEGE = {"/lebt": {"GET"}, "/vergleich": {"POST"}, "/fahrten": {"GET", "POST"}, "/auswertung": {"GET"}}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, adresse, schluessel: str, tarif_ordner: Path, db: Path):
        super().__init__(adresse, Handler)
        self.schluessel = schluessel if len(schluessel) >= SCHLUESSEL_MIN else ""
        self.tarif_ordner = Path(tarif_ordner)
        self.db = Path(db)


class Antwort(Exception):
    def __init__(self, status: int, daten: dict):
        super().__init__(status)
        self.status, self.daten = status, daten


class Handler(BaseHTTPRequestHandler):
    timeout = 30   # Sekunden je Socket-Lesevorgang; hängende Verbindungen blockieren keinen Thread
    server: Server
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:   # Standardprotokoll enthält die Query – abgeschaltet
        pass

    def do_GET(self):
        self._bearbeiten("GET")

    def do_POST(self):
        self._bearbeiten("POST")

    def do_PATCH(self):
        self._bearbeiten("PATCH")

    def do_DELETE(self):
        self._bearbeiten("DELETE")

    def do_PUT(self):
        self._bearbeiten("PUT")

    # ---------- Ablauf ----------

    def _bearbeiten(self, methode: str) -> None:
        beginn = time.monotonic()
        teile = urlsplit(self.path)
        pfad = teile.path
        self._gelesen = False
        try:
            status, daten = self._antwort(methode, pfad, teile.query)
        except Antwort as a:
            status, daten = a.status, a.daten
        except sqlite3.OperationalError:
            status, daten = 503, {"fehler": "Datenbank gerade belegt, bitte erneut versuchen."}
        except Exception as e:   # nie Einzelheiten nach außen
            log.error("Fehler bei %s %s: %s", methode, pfad, type(e).__name__)
            status, daten = 500, {"fehler": "Interner Fehler."}
        if not self._gelesen and self.headers.get("Content-Length", "0") not in ("", "0"):
            self.close_connection = True   # ungelesener Körper darf nicht als nächste Anfrage gelten
        self._senden(status, daten)
        bekannt = pfad if (pfad in WEGE or _FAHRT.match(pfad)) else "(unbekannt)"
        bekannt = "/fahrten/<id>" if _FAHRT.match(pfad) else bekannt
        log.info("%s %s %d %d ms", methode, bekannt, status, (time.monotonic() - beginn) * 1000)

    def _antwort(self, methode: str, pfad: str, query: str) -> tuple[int, dict]:
        if pfad == "/lebt" and methode == "GET":
            return 200, {"ok": True}
        if not self.server.schluessel:
            raise Antwort(503, {"fehler": "Schnittstelle nicht eingerichtet (MOBIL_API_KEY fehlt)."})
        kopf = self.headers.get("Authorization", "")
        erwartet = f"Bearer {self.server.schluessel}"
        if not hmac.compare_digest(kopf.encode(), erwartet.encode()):
            raise Antwort(401, {"fehler": "Nicht angemeldet."})
        treffer = _FAHRT.match(pfad)
        erlaubt = {"GET", "PATCH"} if treffer else WEGE.get(pfad)
        if erlaubt is None:
            raise Antwort(404, {"fehler": "Unbekannter Pfad."})
        if methode not in erlaubt:
            raise Antwort(405, {"fehler": f"Methode {methode} ist hier nicht erlaubt."})
        q = {k: v[-1] for k, v in parse_qs(query, keep_blank_values=True).items()}
        koerper = self._koerper() if methode in ("POST", "PATCH") else None
        tarife = lade_tarife(self.server.tarif_ordner)
        instanz, _ = lade_instanz(self.server.tarif_ordner)
        if pfad == "/vergleich":
            return logik.vergleich(koerper, tarife, instanz)
        con = oeffnen(self.server.db)
        try:
            if treffer and methode == "GET":
                return logik.fahrt(treffer.group(1), con, datetime.now())
            if treffer:
                return logik.rechnung(treffer.group(1), koerper, con)
            if pfad == "/fahrten" and methode == "POST":
                return logik.fahrt_anlegen(koerper, tarife, instanz, con)
            if pfad == "/fahrten":
                return logik.fahrten(q, con, datetime.now())
            return logik.auswertung(q, tarife, con, date.today())
        finally:
            con.close()

    def _koerper(self):
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True   # Körper ohne Längenangabe bleibt ungelesen
            raise Antwort(411, {"fehler": "Bitte mit Content-Length senden."})
        try:
            laenge = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            laenge = -1
        if laenge < 0 or laenge > KOERPER_MAX:
            self.close_connection = True
            raise Antwort(413, {"fehler": f"Anfrage zu groß (höchstens {KOERPER_MAX // 1024} KB)."})
        roh = self.rfile.read(laenge)
        self._gelesen = True
        try:
            return json.loads(roh or b"null")
        except (ValueError, UnicodeDecodeError):
            raise Antwort(400, {"fehler": "Körper ist kein gültiges JSON."}) from None

    def _senden(self, status: int, daten: dict) -> None:
        roh = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(roh)


def baue_server(adresse: tuple[str, int], schluessel: str, tarif_ordner: Path, db: Path) -> Server:
    return Server(adresse, schluessel, tarif_ordner, db)
