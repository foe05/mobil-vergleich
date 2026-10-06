"""Seitentests mit Streamlit AppTest: leerer Verlauf, Eingaben über Seitenwechsel, Ändern in Fahrten."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from engine import Eintrag
from speicher.fahrten import alle, anlegen, oeffnen

WURZEL = Path(__file__).parent.parent


@pytest.fixture
def db(tmp_path, monkeypatch):
    pfad = tmp_path / "mobil.db"
    monkeypatch.setenv("MOBIL_DB", str(pfad))
    st.cache_resource.clear()   # gecachte Verbindung eines früheren Tests verwerfen
    con = oeffnen(pfad)
    yield con
    con.close()
    st.cache_resource.clear()


def fehler(at: AppTest) -> list:
    return [e.value for e in at.exception]


def test_auswertung_nur_kuenftige_fahrt(db):
    s = datetime.now().replace(microsecond=0) + timedelta(days=4)
    anlegen(db, Eintrag(s, s + timedelta(days=1), "Oma", "scouter · M", "Carsharing", 100, 80.0, True))
    at = AppTest.from_file(str(WURZEL / "seiten" / "auswertung.py"), default_timeout=30).run()
    assert fehler(at) == []
    assert any("Verlauf beginnt mit der ersten Fahrt" in c.value for c in at.caption)


def test_vergleich_eingaben_ueberstehen_seitenwechsel(db):
    at = AppTest.from_file(str(WURZEL / "app.py"), default_timeout=30).run()
    at.number_input(key="km").set_value(333).run()
    at.text_input(key="anlass").set_value("Zahnarzt").run()
    at.number_input(key="sixt_preis").set_value(120.0).run()
    at.toggle(key="hund").set_value(False).run()
    at.number_input(key="spritpreis").set_value(1.95).run()
    at.number_input(key="bahn_preis").set_value(80.0).run()
    for seite in ("seiten/fahrten.py", "seiten/auswertung.py", "seiten/vergleich.py"):
        at.switch_page(seite).run()
        assert fehler(at) == []
    z = at.session_state
    assert (z["km"], z["anlass"], z["sixt_preis"], z["hund"], z["spritpreis"], z["bahn_preis"]) == \
        (333, "Zahnarzt", 120.0, False, 1.95, 80.0)
    assert at.number_input(key="km").value == 333 and at.text_input(key="anlass").value == "Zahnarzt"
    assert z["preset"] is None   # Hand-Änderung hat die Vorlage abgewählt und bleibt so


def test_fahrten_anlass_und_eigenauto_aendern(db):
    s = datetime(2026, 9, 1, 10)
    anlegen(db, Eintrag(s, s + timedelta(hours=8), "Oma", "scouter · M", "Carsharing", 100, 80.0, True))
    e = alle(db)[0]
    at = AppTest.from_file(str(WURZEL / "seiten" / "fahrten.py"), default_timeout=30).run()
    at.text_input(key=f"anlass_{e.id}").set_value("Baumarkt")
    at.button_group(key=f"eigen_{e.id}").set_value("nicht gefahren")
    at.button(key=f"aendern_{e.id}").click().run()
    assert fehler(at) == []
    neu = alle(db)[0]
    assert (neu.anlass, neu.eigenauto_gefahren, neu.preis_tatsaechlich) == ("Baumarkt", False, None)
