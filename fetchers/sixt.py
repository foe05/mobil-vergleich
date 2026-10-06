"""Sixt – Platzhalter für Phase 2 (Playwright).

Vorgehen beim Bauen:
1. Mit Playwright (headless Chromium) die Sixt-Suche mit Station Kassel, Datum und Kombi aufrufen.
2. Im Browser-DevTools-Netzwerk-Tab nachsehen, welcher interne JSON-Endpunkt die Preise liefert –
   das ist stabiler als HTML-Parsing.
3. Bot-Schutz einplanen: echte Wartezeiten, wenige Abrufe, keine Parallelisierung.
4. AGB beachten: automatisierte Abfragen sind dort üblicherweise ausgeschlossen.
"""
from engine.modelle import MietAngebot, Szenario

from .base import Fetcher, FetchFehler


class SixtFetcher(Fetcher):
    id = "sixt"
    name = "Sixt"

    def hole_angebot(self, sz: Szenario, station: str, fahrzeugklasse: str) -> MietAngebot:
        raise FetchFehler("Sixt-Abruf noch nicht implementiert (Phase 2)")
