# Entscheidungen festhalten und gegen ein eigenes Auto auswerten

Stand: 2026-10-06 · Status: Entwurf zur Freigabe

## Ziel

Am Ende eines Vergleichs steht eine Entscheidung. Sie wird gespeichert, zusammen mit Mobilitätskosten,
die ohne Vergleich anfallen. Über Monate, Quartale und Jahre beantwortet die App die Leitfrage:

> Lohnt sich doch ein eigenes Auto? Ab wann? Was müssten wir dafür ändern?

Erfolg heißt: Nach einigen Monaten Nutzung zeigt die Auswertung für jedes Referenzprofil, ob es im
gewählten Zeitraum günstiger gewesen wäre, und nennt die Schwelle (km/Jahr bzw. zusätzliche Fahrten),
ab der es sich lohnt.

## Getroffene Entscheidungen

| Frage | Entscheidung |
|---|---|
| Was zählt als Kosten? | Geplanter Preis aus dem Vergleich; tatsächlicher Preis und km optional nachtragbar und dann maßgeblich |
| Womit wird verglichen? | Referenzprofile für ein eigenes Auto in YAML, gepflegt wie die Tarife |
| Was gehört zu den heutigen Kosten? | Nur gespeicherte Einträge. Laufende Posten (z. B. Deutschlandticket) bleiben draußen. Kosten ohne vorherigen Vergleich lassen sich als eigener Eintrag erfassen |
| Welche Fahrten ersetzt ein eigenes Auto? | Pro Eintrag selbst gewählt, ohne Vorgabe. Ein Eintrag kann auch „nicht gefahren“ lauten |
| Wo liegen die Daten? | SQLite-Datei in einem Docker-Volume |

## Nicht im Umfang

Benutzerkonten und „wer hat eingetragen“, laufende Posten, Bearbeitungshistorie, automatischer
Rechnungsimport, Export.

## Bausteine

| Baustein | Aufgabe | Hängt ab von |
|---|---|---|
| `tarife/eigenes_auto.yaml` | Referenzprofile, `typ: eigenauto` | — |
| `engine/tarife.py` | lädt Profile zusätzlich, Rückgabe-Schlüssel `eigenauto` (Liste) | YAML |
| `engine/eigenauto.py` | reine Funktionen: Zeitraumkosten, Break-even, Verlauf | Profile, Einträge als Datenobjekte |
| `speicher/fahrten.py` | einziger SQLite-Zugriff: Schema, anlegen, ändern, nachtragen, löschen, Zeitraum abfragen | Datei unter `MOBIL_DB` |
| `seiten/vergleich.py`, `seiten/fahrten.py`, `seiten/auswertung.py` | Streamlit-Seiten | alles oben |
| `app.py` | Einstieg: Seitenkonfiguration, gemeinsame Gestaltung (CSS, Hell/Dunkel-Knopf), Navigation | Seiten |

Die Engine kennt weder Streamlit noch SQLite. `speicher/` liefert und nimmt Datenobjekte aus
`engine/modelle.py`.

## Datenmodell

### Eintrag (`engine/modelle.py`, Tabelle `eintraege`)

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `id` | int | technisch | Primärschlüssel |
| `angelegt_am` | datetime | technisch | |
| `start`, `ende` | datetime | ja | Reisezeitraum; `start` bestimmt die Zuordnung zu Monat/Quartal/Jahr |
| `anlass` | text | ja | z. B. „Oma“ |
| `ergebnis` | text | ja | Anbieter und Option, z. B. „scouter Kassel · Klasse M (Kombi)“, oder `nicht gefahren` |
| `gruppe` | text | ja | `Carsharing`, `Mietwagen`, `Bahn`, `Sonstiges`, `keine` (nur bei „nicht gefahren“) |
| `km_geplant` | real | ja | |
| `km_tatsaechlich` | real | nein | |
| `preis_geplant` | real | ja | bei „nicht gefahren“ 0 |
| `preis_tatsaechlich` | real | nein | |
| `eigenauto_gefahren` | bool | ja | „Mit eigenem Auto wären wir gefahren“ |
| `vergleich` | JSON | nein | Schnappschuss: Szenario, Annahmen, Rangliste mit Posten, Tarifstand |

Abgeleitet: `km = km_tatsaechlich ?? km_geplant`, `preis = preis_tatsaechlich ?? preis_geplant`,
`gefahren = ergebnis != "nicht gefahren"`, `rechnung_offen = gefahren and preis_tatsaechlich is None and ende < jetzt`.

Schema-Version über `PRAGMA user_version` (Start: 1). WAL-Modus.

### Referenzprofil (`tarife/eigenes_auto.yaml`)

```yaml
typ: eigenauto
profile:
  - id: e-kombi-leasing
    name: E-Kombi Leasing
    quelle: <URL des Angebots/der Quelle>
    stand: "2026-10-06"
    fix_pro_jahr:            # €/Jahr
      rate_oder_wertverlust: 0
      versicherung: 0
      steuer: 0
      wartung: 0
    variabel_pro_km:         # €/km
      energie: 0
      reifen_verschleiss: 0
    hundetauglich: true
    unverifiziert: []        # wie bei den Tarifen: Werte ohne bestätigte Quelle, in der App mit * markiert
```

Startprofile: **E-Kombi Leasing**, **E-Kombi gebraucht gekauft**, **Verbrenner-Kombi gebraucht**.
Die Werte werden bei der Umsetzung recherchiert und mit Quelle und Stand belegt; nicht belegbare Werte
stehen unter `unverifiziert`.

## Rechenlogik (`engine/eigenauto.py`)

Bezeichnungen: `F` = Summe `fix_pro_jahr`, `v` = Summe `variabel_pro_km`.

### Zeitraumkosten

Zeitraum = Kalendermonat, -quartal, -jahr oder „Gesamt“ (erster Eintrag bis heute). Ein laufender
Zeitraum zählt nur bis heute. `tage` = Tage im (ggf. gekürzten) Zeitraum.

- **Ist** = Σ `preis` aller Einträge mit `gefahren`.
- **Mit Profil** = `F × tage / 365`
  + Σ `km × v` aller Einträge mit `eigenauto_gefahren`
  + Σ `preis` aller Einträge mit `gefahren and not eigenauto_gefahren`.
- **Differenz** = Mit Profil − Ist (positiv: Auto wäre teurer gewesen).

### Break-even

Fenster: die letzten 365 Tage bis heute. `spanne` = Tage vom ersten Eintrag im Fenster bis heute,
mindestens 30. Hochrechnungsfaktor `h = 365 / spanne` (1, wenn das Fenster voll ist).

- Basis `B` = Einträge mit `eigenauto_gefahren and gefahren`.
- Heutiger Preis pro km `p = Σ preis(B) / Σ km(B)`.
- Hochgerechnete Fahrleistung `K = h × Σ km` aller Einträge mit `eigenauto_gefahren`.
- Schwelle `K* = F / (p − v)`.
- Fehlende Fahrten `n = (K* − K) / (Σ km(B) / |B|)`, aufgerundet.

Ergebnisse:
- `zu wenig Daten`, wenn `|B| < 3` oder `Σ km(B) = 0`.
- `lohnt sich nie`, wenn `p ≤ v`.
- `lohnt sich bereits`, wenn `K ≥ K*`.
- sonst `K*`, `K`, `n`, angezeigt als Satz: „{Profil} lohnt sich ab ca. {K*} km/Jahr. Ihr kommt
  {hochgerechnet} auf {K} km – etwa {n} weitere Fahrten wie ‚{häufigster Anlass in B}‘ pro Jahr.“

In der App steht die Annahme dabei: zusätzliche km kosten heute denselben Durchschnittspreis `p`.

### Verlauf

Tagesweise kumulierte Werte ab dem ersten Eintrag: Ist (Stufen am `start` jedes Eintrags) und je Profil
`F × t / 365` + kumulierte variable Kosten + kumulierte beibehaltene Kosten.

## Bedienung

Navigation oben: **Vergleich · Fahrten · Auswertung**. Gestaltung, Schriften und Hell/Dunkel-Knopf wie bisher.

**Vergleich** – unter der Rangliste Block „Entscheidung festhalten“: Chips mit allen Optionen der
Rangliste plus „nicht gefahren“; Anlass vorbelegt mit der Vorlage; „Mit eigenem Auto?“
(*wäre gefahren* / *nicht gefahren*) ohne Vorgabe; „Speichern“ erst aktiv, wenn beides gewählt ist.
Gespeichert wird mit Vergleichs-Schnappschuss; kurze Bestätigung.

**Fahrten** – Knopf „Kosten ohne Vergleich eintragen“ (Formular: Datum von/bis, Anlass, Art, Anbieter,
km, Betrag, „Mit eigenem Auto?“). Liste nach Monaten, neueste zuerst, Zeilenstil der Rangliste,
Hinweis „Rechnung offen“. Aufgeklappt: tatsächlichen Preis/km nachtragen, ändern, löschen (mit Rückfrage),
damaligen Vergleich ansehen.

**Auswertung** – Zeitraumart (Monat, Quartal, Jahr, Gesamt) und konkreter Zeitraum. Kernsatz groß, z. B.
„Ein E-Kombi Leasing hätte euch im Q4 2026 312 € mehr gekostet.“ Je Profil: heute, mit Profil,
Differenz, Break-even-Satz. Verlaufsdiagramm (kumuliert, heute gegen Profile). Unten: Annahmen,
Profilstand, Anzahl offener Rechnungen.

## Betrieb

- Compose: Volume `mobil_daten` (fester `name:`), eingehängt unter `/app/daten`; `tarife/` bleibt read-only.
- Dockerfile: `/app/daten` vor `USER appuser` anlegen und dem Benutzer übereignen.
- Umgebungsvariable `MOBIL_DB`, Standard `/app/daten/mobil.db`.
- Host (nicht im Repo): `backup.sh` sichert per SQLite-Backup-API, `restore.sh` legt Volume an und spielt
  zurück, Host-README-Abschnitt, Uptime-Kuma-Monitor auf den Container.

## Fehlerfälle

- Datenbank fehlt oder ist nicht beschreibbar: Vergleich funktioniert; Fahrten und Auswertung zeigen eine
  Fehlermeldung; „Entscheidung festhalten“ meldet den Fehler, statt still zu scheitern.
- Fehlerhaftes Profil: wird mit Hinweis übersprungen, andere Profile bleiben.
- Gespeicherte Vergleiche sind Schnappschüsse; Tarifänderungen wirken nicht rückwirkend.
- Ein Eintrag ohne Vergleich hat `vergleich = NULL`; die Oberfläche zeigt dann keinen Vergleichsbereich.

## Tests

Testgetrieben, `pytest` mit neuer `pytest.ini` (`pythonpath = .`), damit `pytest -q` laut README läuft.

- `tests/test_eigenauto.py`: anteilige Fixkosten inkl. laufendem Zeitraum; die vier Kombinationen
  gefahren × eigenauto_gefahren; tatsächlicher vor geplantem Wert; Break-even Normalfall, `lohnt sich nie`,
  `lohnt sich bereits`, `zu wenig Daten`, Hochrechnung bei kurzer Spanne.
- `tests/test_speicher.py` gegen temporäre Datei: Schema idempotent, anlegen, nachtragen, ändern, löschen,
  Zeitraumabfrage, Schnappschuss-Rundreise.
- `tests/test_engine.py`: Profil-Laden ergänzt; bestehende 8 Tests bleiben grün.
- Abschluss: Browser-Durchlauf (Entscheidung speichern, Kosten ohne Vergleich, Rechnung nachtragen,
  Auswertung) in hell und dunkel, mobil und Desktop.
