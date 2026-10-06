# Entscheidungen und Eigenauto-Auswertung – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entscheidungen und Kosten ohne Vergleich in SQLite speichern und je Zeitraum gegen Referenzprofile eines eigenen Autos auswerten, inklusive Break-even.

**Architecture:** Reine Rechenlogik in `engine/` (ohne Streamlit/SQLite), Datenzugriff gekapselt in `speicher/fahrten.py`, Oberfläche als drei Streamlit-Seiten unter `seiten/` mit gemeinsamem Einstieg `app.py`. Profile in `tarife/eigenes_auto.yaml`, Daten im Volume `mobil_daten`.

**Tech Stack:** Python 3.12, Streamlit 1.65, sqlite3 (Standardbibliothek), PyYAML, Altair 6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-entscheidungen-und-eigenauto-design.md`

## Global Constraints

- Bedienoberfläche, Kommentare und Bezeichner deutsch, wie im bestehenden Code.
- `engine/` importiert weder `streamlit` noch `sqlite3`.
- Geldbeträge mit `euro()` aus der App formatiert (deutsches Format), km mit `zahl()`.
- Gestaltung: bestehende CSS-Variablen (`--akzent`, `--tinte`, `--leise`, `--linie`, `--spur` …) und Klassen der Rangliste wiederverwenden; Hell und Dunkel müssen funktionieren.
- Datenbankpfad aus Umgebungsvariable `MOBIL_DB`, Standard `/app/daten/mobil.db`; Schema-Version `PRAGMA user_version = 1`; WAL-Modus.
- Volume-Name exakt `mobil_daten`, Einhängepunkt `/app/daten`.
- Konstante `NICHT_GEFAHREN = "nicht gefahren"`; Gruppen exakt `Carsharing`, `Mietwagen`, `Bahn`, `Sonstiges`, `keine`.
- Bestehende 8 Tests bleiben grün; `pytest -q` (ohne `python -m`) muss laufen.

## Review Focus

1. Eintrag mit 0 km (z. B. Taxi-Pauschale als „Sonstiges“) – Preis zählt, keine Division durch null im Break-even.
2. Eintrag mit `start` in der Zukunft (geplante Reise) – zählt im eigenen Zeitraum, bleibt aber aus dem Break-even-Fenster.
3. Formular „Kosten ohne Vergleich“ mit Rückgabe vor Abholung oder negativem Betrag – wird abgelehnt, nichts gespeichert.
4. Datenbankverzeichnis fehlt beim ersten Start bzw. zweiter Container-Start – Schema wird angelegt bzw. ohne Fehler erneut geprüft.
5. Profil-YAML mit fehlendem Pflichtfeld – Profil wird übersprungen, Hinweis erscheint, übrige Profile bleiben.

---

### Task 1: Datenmodelle, Profil-Laden, Referenzprofile, pytest-Konfiguration

**Files:**
- Create: `pytest.ini`, `tarife/eigenes_auto.yaml`
- Modify: `engine/modelle.py`, `engine/tarife.py`, `engine/__init__.py`
- Test: `tests/test_eigenauto.py` (neu, Abschnitt Profile)

**Interfaces:**
- Produces (`engine/modelle.py`):
  - `NICHT_GEFAHREN: str = "nicht gefahren"`
  - `@dataclass Eintrag(start: datetime, ende: datetime, anlass: str, ergebnis: str, gruppe: str, km_geplant: float, preis_geplant: float, eigenauto_gefahren: bool, km_tatsaechlich: float | None = None, preis_tatsaechlich: float | None = None, vergleich: dict | None = None, id: int | None = None, angelegt_am: datetime | None = None)` mit Properties `km`, `preis`, `gefahren` und Methode `rechnung_offen(jetzt: datetime) -> bool` (Formeln laut Spec „Abgeleitet“).
  - `@dataclass Profil(id: str, name: str, quelle: str, stand: str, fix_pro_jahr: dict[str, float], variabel_pro_km: dict[str, float], hundetauglich: bool = True, unverifiziert: list[str] = [])` (via `field(default_factory=list)`) mit Properties `fix: float` (Summe) und `variabel: float` (Summe).
- Produces (`engine/tarife.py`): `lade_tarife(ordner)` liefert zusätzlich `"eigenauto": list[Profil]` und `"hinweise": list[str]`.
- Exports in `engine/__init__.py`: `Eintrag`, `Profil`, `NICHT_GEFAHREN`.

- [ ] **Step 1: `pytest.ini` anlegen** mit `[pytest]` / `pythonpath = .` / `testpaths = tests`. Prüfen: `pytest -q` → `8 passed`.

- [ ] **Step 2: Failing tests schreiben** in `tests/test_eigenauto.py`:

```python
def test_profil_summen():
    p = Profil("x", "X", "q", "2026-10-06", {"a": 3000, "b": 650}, {"e": 0.08, "r": 0.02})
    assert p.fix == 3650 and p.variabel == pytest.approx(0.10)

def test_eintrag_tatsaechlich_vor_geplant():
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter", "Carsharing",
                100, 92.49, True, km_tatsaechlich=110, preis_tatsaechlich=100)
    assert (e.km, e.preis, e.gefahren) == (110, 100, True)

def test_rechnung_offen():
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter", "Carsharing", 100, 92.49, True)
    assert e.rechnung_offen(datetime(2026, 10, 12)) and not e.rechnung_offen(datetime(2026, 10, 11, 12))
    assert not replace(e, ergebnis=NICHT_GEFAHREN).rechnung_offen(datetime(2026, 10, 12))

def test_profile_laden_mit_fehlerhaftem(tmp_path):
    (tmp_path / "eigenes_auto.yaml").write_text(
        "typ: eigenauto\nprofile:\n"
        "  - {id: ok, name: OK, quelle: q, stand: '2026-10-06', fix_pro_jahr: {a: 1}, variabel_pro_km: {e: 0.1}}\n"
        "  - {id: kaputt, name: Kaputt}\n", encoding="utf-8")
    t = lade_tarife(tmp_path)
    assert [p.id for p in t["eigenauto"]] == ["ok"] and "Kaputt" in t["hinweise"][0]

def test_echte_profile_laden():
    t = lade_tarife(Path(__file__).parent.parent / "tarife")
    assert {p.id for p in t["eigenauto"]} == {"e-kombi-leasing", "e-kombi-gebraucht", "verbrenner-kombi-gebraucht"}
    assert all(p.fix > 0 and p.variabel > 0 for p in t["eigenauto"])
```

- [ ] **Step 3: Tests laufen lassen** – `pytest tests/test_eigenauto.py -q` → FAIL (ImportError).

- [ ] **Step 4: Modelle und Loader implementieren.** Pflichtfelder eines Profils: `id`, `name`, `quelle`, `stand`, `fix_pro_jahr`, `variabel_pro_km`; fehlt eines, Hinweis `f"Profil „{name or id}“ übersprungen: {feld} fehlt"`.

- [ ] **Step 5: Referenzprofile recherchieren und `tarife/eigenes_auto.yaml` schreiben** – Format laut Spec, ids `e-kombi-leasing`, `e-kombi-gebraucht`, `verbrenner-kombi-gebraucht`. Kassel/Familie mit Hund: Kombi-Größe (z. B. Skoda Enyaq/ID.7 Tourer bzw. Octavia Combi). Jeder Wert mit Kommentar zur Quelle; nicht belegte Werte in `unverifiziert`. Stand-Datum 2026-10-06.

- [ ] **Step 6: Tests laufen lassen** – `pytest -q` → alle grün (8 alt + 5 neu).

- [ ] **Step 7: Commit** – `git add pytest.ini engine tarife/eigenes_auto.yaml tests/test_eigenauto.py && git commit -m "feat: Eintrag/Profil-Modelle und Referenzprofile eigenes Auto"`

---

### Task 2: Zeiträume und Zeitraumkosten

**Files:**
- Create: `engine/eigenauto.py`
- Test: `tests/test_eigenauto.py`

**Interfaces:**
- Consumes: `Eintrag`, `Profil` (Task 1)
- Produces:
  - `@dataclass Zeitraum(art: str, von: date, bis: date, label: str)` mit Property `tage: int` (`(bis - von).days + 1`); `art` ∈ `"monat" | "quartal" | "jahr" | "gesamt"`; Labels `"Oktober 2026"`, `"Q4 2026"`, `"2026"`, `"Gesamt"`.
  - `zeitraum(art: str, bezug: date, heute: date, erster: date | None = None) -> Zeitraum` – Kalenderzeitraum, der `bezug` enthält; `bis` auf `heute` gekürzt; bei `"gesamt"` `von = erster`.
  - `zeitraeume(art: str, eintraege: list[Eintrag], heute: date) -> list[Zeitraum]` – alle Zeiträume mit mindestens einem Eintrag, neueste zuerst (bei `"gesamt"` genau einer).
  - `@dataclass ZeitraumKosten(ist: float, mit_profil: float, differenz: float)`
  - `zeitraumkosten(eintraege: list[Eintrag], profil: Profil, zr: Zeitraum) -> ZeitraumKosten` – Formeln laut Spec; ein Eintrag gehört zum Zeitraum, wenn `zr.von <= e.start.date() <= zr.bis`. Beträge auf 2 Stellen gerundet.

- [ ] **Step 1: Failing tests schreiben.** Gemeinsame Testdaten als Fixture `vier_faelle` (Profil F = 3650, v = 0,10):
  - a) gefahren, mit Auto: 100 km, 92,49 € · b) nicht gefahren, mit Auto: 200 km · c) Bahn, ohne Auto: 300 km, 120 € · d) nicht gefahren, ohne Auto: 50 km; alle im Oktober 2026.

```python
def test_quartal_vier_faelle(vier_faelle, profil):
    zr = zeitraum("quartal", date(2026, 10, 10), heute=date(2027, 1, 15))
    assert (zr.von, zr.bis, zr.tage, zr.label) == (date(2026, 10, 1), date(2026, 12, 31), 92, "Q4 2026")
    k = zeitraumkosten(vier_faelle, profil, zr)
    assert (k.ist, k.mit_profil, k.differenz) == (212.49, 1070.0, 857.51)

def test_laufender_zeitraum_bis_heute(vier_faelle, profil):
    zr = zeitraum("quartal", date(2026, 10, 10), heute=date(2026, 11, 15))
    assert zr.tage == 46 and zeitraumkosten(vier_faelle, profil, zr).mit_profil == 460.0 + 30 + 120

def test_eintrag_ohne_km_zaehlt_preis(profil):
    taxi = Eintrag(datetime(2026, 10, 3), datetime(2026, 10, 3), "Taxi", "Taxi", "Sonstiges", 0, 25, True)
    k = zeitraumkosten([taxi], profil, zeitraum("monat", date(2026, 10, 3), heute=date(2026, 11, 1)))
    assert k.ist == 25 and k.mit_profil == 310.0

def test_zeitraeume_liste(vier_faelle):
    assert [z.label for z in zeitraeume("monat", vier_faelle, date(2027, 1, 15))] == ["Oktober 2026"]
    assert zeitraeume("gesamt", vier_faelle, date(2027, 1, 15))[0].von == date(2026, 10, 1)
```

(Fixture so wählen, dass der früheste Eintrag am 2026-10-01 liegt.)

- [ ] **Step 2: Tests laufen lassen** – FAIL (ImportError).
- [ ] **Step 3: Implementieren** in `engine/eigenauto.py`.
- [ ] **Step 4: Tests laufen lassen** – `pytest -q` grün.
- [ ] **Step 5: Commit** – `feat: Zeiträume und Zeitraumkosten gegen eigenes Auto`

---

### Task 3: Break-even und Verlauf

**Files:**
- Modify: `engine/eigenauto.py`
- Test: `tests/test_eigenauto.py`

**Interfaces:**
- Produces:
  - `@dataclass BreakEven(status: str, schwelle_km: float | None = None, km_jahr: float | None = None, weitere_fahrten: int | None = None, hochgerechnet: bool = False, anlass: str | None = None)`; `status` ∈ `"zu_wenig_daten" | "nie" | "bereits" | "schwelle"`.
  - `break_even(eintraege: list[Eintrag], profil: Profil, heute: date) -> BreakEven` – Formeln laut Spec. Fenster: `heute - 365 Tage < start.date() <= heute` (Zukunft ausgeschlossen). `spanne`: 365, wenn es Einträge vor dem Fenster gibt, sonst Tage vom ersten Eintrag im Fenster bis `heute`, mindestens 30. `weitere_fahrten` mit `math.ceil`. `anlass` = häufigster Anlass in B.
  - `verlauf(eintraege: list[Eintrag], profile: list[Profil], heute: date) -> list[dict]` – Zeilen `{"datum": date, "reihe": str, "kumuliert": float}`, Reihe `"Heute"` plus je Profil `profil.name`; ein Punkt pro Tag vom ersten Eintrag bis `heute`; Fixkostenanteil am Tag `d` = `F × ((d − erster).days + 1) / 365`.

- [ ] **Step 1: Failing tests schreiben.** Basis: drei Einträge „Oma“, je 100 km / 50 € mit Auto (p = 0,50), dazu ein älterer Eintrag vor dem Fenster **als letztes Listenelement**, heute 2027-10-01.

```python
def test_break_even_schwelle(basis, profil):            # F 3650, v 0.10 -> K* = 9125
    b = break_even(basis, profil, date(2027, 10, 1))
    assert (b.status, b.schwelle_km, b.km_jahr, b.weitere_fahrten, b.anlass, b.hochgerechnet) == \
           ("schwelle", 9125, 300, 89, "Oma", False)

def test_break_even_nie(basis):
    assert break_even(basis, Profil("x", "X", "q", "s", {"a": 3650}, {"e": 0.6}), date(2027, 10, 1)).status == "nie"

def test_break_even_bereits(basis):
    assert break_even(basis, Profil("x", "X", "q", "s", {"a": 10}, {"e": 0.1}), date(2027, 10, 1)).status == "bereits"

def test_break_even_zu_wenig_daten(basis, profil):
    assert break_even(basis[:2], profil, date(2027, 10, 1)).status == "zu_wenig_daten"   # nur 2 in B

def test_break_even_hochrechnung(profil):   # erster Eintrag 2027-01-01, heute 2027-01-31 -> h = 365/30
    b = break_even(drei_oma_ab(date(2027, 1, 1)), profil, date(2027, 1, 31))
    assert b.hochgerechnet and b.km_jahr == pytest.approx(3650)

def test_break_even_mindestspanne(profil):  # erster Eintrag 2027-01-25, heute 2027-01-31 -> spanne 30
    assert break_even(drei_oma_ab(date(2027, 1, 25)), profil, date(2027, 1, 31)).km_jahr == pytest.approx(3650)

def test_break_even_ignoriert_zukunft(basis, profil):
    zukunft = replace(basis[0], start=datetime(2027, 12, 1), ende=datetime(2027, 12, 2))
    assert break_even(basis + [zukunft], profil, date(2027, 10, 1)).km_jahr == 300

def test_verlauf_endwerte(vier_faelle, profil):
    zeilen = verlauf(vier_faelle, [profil], date(2026, 12, 31))
    ende = {z["reihe"]: z["kumuliert"] for z in zeilen if z["datum"] == date(2026, 12, 31)}
    assert ende["Heute"] == 212.49 and ende[profil.name] == pytest.approx(920 + 30 + 120)
```

(`drei_oma_ab(d)` = Hilfsfunktion im Test: drei „Oma“-Einträge ab Tag `d`, jeweils einen Tag versetzt.)

- [ ] **Step 2: Tests laufen lassen** – FAIL.
- [ ] **Step 3: Implementieren.**
- [ ] **Step 4: Tests laufen lassen** – `pytest -q` grün.
- [ ] **Step 5: Commit** – `feat: Break-even und Kostenverlauf eigenes Auto`

---

### Task 4: Speicher (SQLite)

**Files:**
- Create: `speicher/__init__.py`, `speicher/fahrten.py`
- Test: `tests/test_speicher.py`

**Interfaces:**
- Consumes: `Eintrag` (Task 1)
- Produces (`speicher/fahrten.py`), alle mit Pfad-Parameter für Tests:
  - `db_pfad() -> Path` – `MOBIL_DB` oder `/app/daten/mobil.db`
  - `oeffnen(pfad: Path) -> sqlite3.Connection` – legt Elternverzeichnis und Schema an (`CREATE TABLE IF NOT EXISTS eintraege …` laut Spec-Datenmodell, `vergleich` als TEXT mit JSON), setzt `journal_mode=WAL`, `user_version=1`.
  - `anlegen(con, e: Eintrag) -> int`, `aendern(con, e: Eintrag) -> None` (per `e.id`), `loeschen(con, id: int) -> None`, `alle(con) -> list[Eintrag]` (neueste `start` zuerst).
  - Datumswerte als ISO-Text, bool als 0/1.

- [ ] **Step 1: Failing tests schreiben**

```python
def test_schema_idempotent(tmp_path):
    p = tmp_path / "unter" / "mobil.db"           # Verzeichnis existiert noch nicht
    oeffnen(p).close(); con = oeffnen(p)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 1

def test_rundreise_mit_vergleich(tmp_path):
    con = oeffnen(tmp_path / "m.db")
    e = Eintrag(datetime(2026, 10, 10, 10), datetime(2026, 10, 11, 16), "Oma", "scouter", "Carsharing",
                100, 92.49, True, vergleich={"rangliste": [{"anbieter": "scouter", "gesamt": 92.49}]})
    e.id = anlegen(con, e)
    assert alle(con) == [replace(e, angelegt_am=alle(con)[0].angelegt_am)]

def test_nachtragen_und_loeschen(tmp_path):
    con = oeffnen(tmp_path / "m.db")
    e = replace(BEISPIEL); e.id = anlegen(con, e)
    aendern(con, replace(e, preis_tatsaechlich=101.5, km_tatsaechlich=104))
    assert alle(con)[0].preis == 101.5
    loeschen(con, e.id); assert alle(con) == []

def test_sortierung(tmp_path):
    con = oeffnen(tmp_path / "m.db")
    for tag in (3, 20, 11):
        anlegen(con, replace(BEISPIEL, start=datetime(2026, 10, tag), ende=datetime(2026, 10, tag, 18)))
    assert [e.start.day for e in alle(con)] == [20, 11, 3]
```

- [ ] **Step 2: Tests laufen lassen** – FAIL.
- [ ] **Step 3: Implementieren.**
- [ ] **Step 4: Tests laufen lassen** – `pytest -q` grün.
- [ ] **Step 5: Commit** – `feat: SQLite-Speicher für Einträge`

---

### Task 5: App aufteilen, Navigation, „Entscheidung festhalten“

**Files:**
- Create: `seiten/__init__.py`, `seiten/gemeinsam.py`, `seiten/vergleich.py`
- Modify: `app.py`

**Interfaces:**
- Consumes: `speicher.fahrten.oeffnen/anlegen/db_pfad`, `Eintrag`, `NICHT_GEFAHREN`
- Produces (`seiten/gemeinsam.py`): `euro()`, `zahl()`, `zeitpunkt()`, `PALETTEN`, `GRUPPENFARBEN`, `modus()`, `gestaltung()` (CSS + Hell/Dunkel-Knopf, aus heutigem `app.py` verschoben), `tarife()` (gecacht), `verbindung() -> sqlite3.Connection | None` (bei Fehler `None` und `st.error` mit Ursache, gecacht per `st.cache_resource`).
- `app.py`: `set_page_config`, `gestaltung()`, `st.navigation([Vergleich, Fahrten, Auswertung], position="top").run()`; Seiten `seiten/fahrten.py` und `seiten/auswertung.py` zunächst mit Überschrift als Platzhalter-Inhalt, gefüllt in Task 6/7.

- [ ] **Step 1: Verschieben ohne Verhaltensänderung** – Vergleichsseite nach `seiten/vergleich.py`, Gemeinsames nach `seiten/gemeinsam.py`. Prüfen: Container neu bauen, Playwright-Screenshot mobil/desktop (Skript aus der Sitzung, `locale="de-DE"`) zeigt dieselbe Seite plus Navigation, keine `stException`.
- [ ] **Step 2: Block „Entscheidung festhalten“** unter der Rangliste: `st.pills` mit `[f"{e.anbieter} · {e.option}" for e in ergebnisse] + [NICHT_GEFAHREN]`, `st.text_input("Anlass", value=<Vorlage ohne Klammerzusatz>)`, `st.segmented_control("Mit eigenem Auto?", ["wäre gefahren", "nicht gefahren"])` ohne Vorgabe, `st.button("Speichern", disabled=<eines fehlt>)`. Gespeichert wird `Eintrag` mit `km_geplant=sz.km`, `preis_geplant=gewähltes.gesamt` (bzw. 0), `gruppe` aus Ergebnis (bzw. `"keine"`), `vergleich={"szenario": {...start, ende, km, spritpreis, hund...}, "rangliste": [{anbieter, option, gruppe, gesamt, posten}], "tarifstand": {name: stand}}`; danach `st.toast("Gespeichert")`. Bei `verbindung() is None` ist der Block durch die Fehlermeldung ersetzt.
- [ ] **Step 3: Prüfen** – Playwright: Option wählen, „wäre gefahren“, Speichern → Toast; `docker exec mobil-vergleich python -c` liest 1 Eintrag aus `/app/daten/mobil.db` (Volume erst in Task 8 – bis dahin legt der Container die DB im Image-Pfad an; das reicht für diesen Test). `pytest -q` grün.
- [ ] **Step 4: Commit** – `feat: Navigation und Entscheidung festhalten`

---

### Task 6: Seite „Fahrten“

**Files:**
- Modify: `seiten/fahrten.py`

**Interfaces:**
- Consumes: `alle/anlegen/aendern/loeschen`, `verbindung()`, `euro()`, Rangliste-CSS (`.rang`)

- [ ] **Step 1: Formular „Kosten ohne Vergleich eintragen“** in `st.dialog`: Abholung (Datum+Zeit), Rückgabe, Anlass, Art (`Carsharing`, `Mietwagen`, `Bahn`, `Sonstiges`), Anbieter (Text, wird `ergebnis`), km (≥ 0), Betrag (≥ 0, wird `preis_geplant` **und** `preis_tatsaechlich`), „Mit eigenem Auto?“ ohne Vorgabe. Speichern nur, wenn Rückgabe > Abholung und Auswahl getroffen; sonst Fehlermeldung im Dialog, nichts gespeichert.
- [ ] **Step 2: Liste** – nach Monat gruppiert (Überschrift „Oktober 2026“), neueste zuerst, je Eintrag eine Zeile im Rangliste-Stil: Datum, Anlass, Ergebnis, Betrag (tatsächlich, sonst geplant), Marke „Rechnung offen“ (`rechnung_offen(datetime.now())`), Marke „mit Auto: ja/nein“. Je Eintrag `st.expander` (oder `st.popover`) mit: Felder tatsächlicher Preis/km + „Nachtragen“, „Löschen“ mit Bestätigungs-Checkbox, damalige Rangliste (aus `vergleich`) als Liste, wenn vorhanden.
- [ ] **Step 3: Prüfen** – Playwright: Taxi 25 €, 0 km, Sonstiges, „wäre gefahren“ speichern → erscheint; Rückgabe vor Abholung → Fehlermeldung, Anzahl Einträge unverändert; Rechnung nachtragen → „Rechnung offen“ verschwindet; löschen. Hell und dunkel.
- [ ] **Step 4: Commit** – `feat: Seite Fahrten mit Nachtragen und Kosten ohne Vergleich`

---

### Task 7: Seite „Auswertung“

**Files:**
- Modify: `seiten/auswertung.py`

**Interfaces:**
- Consumes: `zeitraum/zeitraeume/zeitraumkosten/break_even/verlauf` (Task 2/3), `tarife()["eigenauto"]` und `["hinweise"]`, `alle()`

- [ ] **Step 1: Zeitraumwahl** – `st.segmented_control` Monat/Quartal/Jahr/Gesamt (Vorgabe Quartal), daneben `st.selectbox` mit `zeitraeume(...)` (Labels). Ohne Einträge: Hinweis „Noch keine Fahrten gespeichert“ und Ende.
- [ ] **Step 2: Kernsatz** im `.sieger`-Stil für das Profil mit der kleinsten Differenz: „Ein {name} hätte euch im {label} {euro(|d|)} {mehr|weniger} gekostet.“
- [ ] **Step 3: Profilzeilen** im `.rang`-Stil: heute / mit Profil / Differenz, darunter Break-even-Satz je Status: `schwelle` laut Spec-Satz (mit „hochgerechnet“ nur bei `hochgerechnet`), `bereits` „{name} hätte sich in den letzten 12 Monaten schon gelohnt.“, `nie` „{name} lohnt sich mit eurem Fahrprofil nicht – schon die km-Kosten liegen über eurem heutigen Preis pro km.“, `zu_wenig_daten` „Für eine Schwelle braucht es mindestens drei Fahrten, die ihr mit eigenem Auto gemacht hättet.“ Profile mit `unverifiziert` mit `*`.
- [ ] **Step 4: Verlaufsdiagramm** – vor dem Code den `dataviz`-Skill laden; Altair-Linien aus `verlauf()`, Farben aus `GRUPPENFARBEN[modus()]`-Logik bzw. Theme-`chartCategoricalColors`, Hell/Dunkel lesbar.
- [ ] **Step 5: Fußbereich** – Annahme zum Durchschnittspreis, Profilstände mit Quelle, Anzahl offener Rechnungen, `hinweise` aus dem Loader.
- [ ] **Step 6: Prüfen** – Playwright mit den Einträgen aus Task 5/6: Zahlen stimmen mit einer Handrechnung nach Spec überein, Diagramm sichtbar, keine `stException`, hell/dunkel, mobil/desktop.
- [ ] **Step 7: Commit** – `feat: Seite Auswertung mit Break-even und Verlauf`

---

### Task 8: Betrieb, Host-Einbindung, Abschluss

**Files:**
- Modify: `docker-compose.yml`, `Dockerfile`, `README.md`
- Host (nicht im Repo): `~/backup.sh`, `~/restore.sh` (+ zugehörige READMEs), `~/docker-apps/README.md`, Uptime-Kuma-DB

- [ ] **Step 1: Compose/Dockerfile** – Volume `mobil_daten` (`volumes: mobil_daten: {name: mobil_daten}`), Mount `mobil_daten:/app/daten`; im Dockerfile `RUN mkdir -p /app/daten` vor dem `chown`. Neu bauen; Test-DB aus Task 5–7 vorher löschen (liegt im Container, nicht im Volume). Prüfen: `docker exec mobil-vergleich touch /app/daten/x && rm` als `appuser` klappt; Eintrag speichern, Container neu erstellen (`up -d --force-recreate`), Eintrag noch da.
- [ ] **Step 2: README des Repos** – Abschnitt „Fahrten und Auswertung“ (Volume, `MOBIL_DB`, Profile pflegen), `pytest -q` stimmt jetzt.
- [ ] **Step 3: Host-Backup** – `backup.sh`: `docker exec mobil-vergleich python -c "import sqlite3; s=sqlite3.connect('/app/daten/mobil.db'); d=sqlite3.connect('/tmp/mobil.db'); s.backup(d)"` + `docker cp` ins Backup-Verzeichnis als `mobil_db_<datum>.sqlite`; `restore.sh`: Volume anlegen, Datei hineinkopieren. Testen nach dem in der Memory beschriebenen Verfahren (Kopie bis vor GPG, `BACKUP_DIR` im Scratchpad, Exit 0); vorher `.bak-20261006` anlegen.
- [ ] **Step 4: Host-README und Kuma** – Abschnitt mobil-vergleich (eigenes Projekt, Netz, Volume, Start); Kuma-Docker-Monitor auf Containernamen `mobil-vergleich` als SQL-Kopie eines bestehenden Monitors (Memory „Kuma-Docker-Monitore auf Namen“).
- [ ] **Step 5: Abschluss-Durchlauf** – `pytest -q` grün; Playwright-Durchlauf laut Spec „Tests/Abschluss“; Testeinträge danach löschen.
- [ ] **Step 6: Commit und Push** – `git commit -m "feat: Daten-Volume und Doku"`; `git push git@github.com:foe05/mobil-vergleich.git main`.
