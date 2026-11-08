"""Start: python -m schnittstelle (Compose-Dienst mobil-api)."""
import logging
import os
from pathlib import Path

from schnittstelle.server import SCHLUESSEL_MIN, baue_server
from speicher.fahrten import db_pfad

PORT = 8502


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log = logging.getLogger("mobil-api")
    schluessel = os.environ.get("MOBIL_API_KEY", "").strip()
    if len(schluessel) < SCHLUESSEL_MIN:
        log.warning("MOBIL_API_KEY fehlt oder ist kürzer als %d Zeichen – nur /lebt antwortet, alles andere mit 503.",
                    SCHLUESSEL_MIN)
    srv = baue_server(("0.0.0.0", PORT), schluessel, Path(__file__).parent.parent / "tarife", db_pfad())
    log.info("Schnittstelle läuft auf Port %d", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
