"""Instanz-Einstellungen: Ort, Reisende, Hund, Reise-Vorlagen."""
from datetime import date, time
from pathlib import Path

from engine import Instanz, lade_instanz, reisende_text, vorlage_zeiten

TARIFE = Path(__file__).parent.parent / "tarife"


def test_ohne_datei_gelten_die_bisherigen_werte(tmp_path):
    i, hinweise = lade_instanz(tmp_path)
    assert (i.ort, i.personen, i.hund, hinweise) == ("Kassel", 4, True, [])
    assert [v.name for v in i.vorlagen] == ["IKEA-Nachmittag", "Oma (1 Nacht)", "Langes Wochenende",
                                            "Urlaub (2 Wochen)"]


def test_echte_datei_entspricht_den_bisherigen_werten(tmp_path):
    assert lade_instanz(TARIFE)[0] == lade_instanz(tmp_path)[0]


def test_eigene_werte(tmp_path):
    (tmp_path / "instanz.yaml").write_text(
        "ort: Göttingen\npersonen: 2\nhund: false\nvorlagen:\n"
        "  - {name: Baumarkt, start_tag: mi, start: '09:30', tage: 0, ende: '12:00', km: 20}\n",
        encoding="utf-8")
    i, hinweise = lade_instanz(tmp_path)
    assert (i.ort, i.personen, i.hund, hinweise) == ("Göttingen", 2, False, [])
    v = i.vorlagen[0]
    assert (v.name, v.start_tag, v.start, v.tage, v.ende, v.km) == ("Baumarkt", 2, time(9, 30), 0, time(12), 20)


def test_kaputte_datei_ergibt_hinweis_und_standard(tmp_path):
    (tmp_path / "instanz.yaml").write_text("ort: [kaputt\n", encoding="utf-8")
    i, hinweise = lade_instanz(tmp_path)
    assert i == lade_instanz(tmp_path / "gibtsnicht")[0]
    assert "instanz.yaml" in hinweise[0]


def test_kaputte_vorlage_wird_uebersprungen(tmp_path):
    (tmp_path / "instanz.yaml").write_text(
        "vorlagen:\n  - {name: Gut, start_tag: sa, start: '10:00', tage: 1, ende: '16:00', km: 100}\n"
        "  - {name: Kaputt, start_tag: xx}\n", encoding="utf-8")
    i, hinweise = lade_instanz(tmp_path)
    assert [v.name for v in i.vorlagen] == ["Gut"] and "Kaputt" in hinweise[0]


def test_reisende_text():
    assert reisende_text(Instanz(personen=4, hund=True)) == "4 Personen und Hund"
    assert reisende_text(Instanz(personen=1, hund=False)) == "1 Person"


def test_vorlage_zeiten_naechster_wochentag():
    oma = lade_instanz(Path("/gibtsnicht"))[0].vorlagen[1]
    # Montag 2026-10-05 -> nächster Samstag 10.10.; an einem Samstag selbst eine Woche später
    assert vorlage_zeiten(oma, date(2026, 10, 5)) == (date(2026, 10, 10), time(10), date(2026, 10, 11), time(16), 100)
    assert vorlage_zeiten(oma, date(2026, 10, 10))[0] == date(2026, 10, 17)
