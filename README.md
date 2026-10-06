# Wie fahren wir? – Mobilitäts-Vergleich

Selbstgehostetes Vergleichstool für eine Familie (4 Personen + Hund) in Kassel:
scouter, Flinkster, Sixt, Europcar, Getaround und Bahn für typische Reisen
(IKEA-Nachmittag, Oma mit Übernachtung, langes Wochenende, Urlaub).

## Aufbau

```
tarife/      YAML je Anbieter und Eigenauto-Profile – hier werden Preise gepflegt
engine/      Preislogik und Auswertung (reine Python-Funktionen, getestet)
speicher/    SQLite-Zugriff für Entscheidungen und Fahrten
seiten/      Streamlit-Seiten: Vergleich, Fahrten, Auswertung
fetchers/    Phase 2: automatischer Abruf Sixt/Europcar (noch Platzhalter)
app.py       Streamlit-Oberfläche
tests/       Tests gegen offizielle Preisbeispiele der Anbieter
```

## Lokal starten

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q                 # sollte 34 grüne Tests zeigen
MOBIL_DB=./daten/mobil.db streamlit run app.py   # http://localhost:8501
```

Lokal liegt die Datenbank unter dem Pfad aus `MOBIL_DB` (hier `./daten/mobil.db`);
ohne die Variable würde die App `/app/daten/mobil.db` verwenden, den Pfad im Container.

## Auf dem Hetzner-Server (Docker + Nginx Proxy Manager)

1. Repo nach `~/docker-apps/mobil-vergleich` klonen.
2. NPM-Netzwerk herausfinden: `docker network ls` – Namen ggf. in `.env` setzen:
   `PROXY_NETWORK=dein_netzwerkname`
3. `docker compose up -d --build`
4. Im NPM einen Proxy Host anlegen:
   - Domain z. B. `mobil.broetzens.de`, Forward Host `mobil-vergleich`, Port `8501`
   - **Websockets Support einschalten** (sonst bleibt Streamlit leer)
   - SSL per Let's Encrypt, „Force SSL“
   - **Access List** mit Basic Auth für euch beide anlegen und zuweisen
5. Link an deine Frau schicken, auf dem Handy zum Startbildschirm hinzufügen.

## Fahrten und Auswertung

- **Vergleich**: Preise der Anbieter für eine Fahrt; das Ergebnis lässt sich als Entscheidung speichern.
- **Fahrten**: gespeicherte Entscheidungen, Kosten ohne Vergleich eintragen, tatsächliche Rechnung nachtragen.
- **Auswertung**: Hätte sich ein eigenes Auto gelohnt? Break-even je Profil, Verlauf und was sich ändern müsste.

Die Daten liegen in SQLite im Docker-Volume `mobil_daten` (`/app/daten/mobil.db`, Pfad per
Umgebungsvariable `MOBIL_DB`). Das Volume überlebt `docker compose up -d --build` und Neuanlegen
des Containers; es heißt fest `mobil_daten`, unabhängig vom Compose-Projektnamen.

Die Profile für das eigene Auto stehen in `tarife/eigenes_auto.yaml`. Es gelten dieselben Regeln
wie bei den Tarifen: jede Zahl mit `quelle` und `stand`, Geschätztes unter `unverifiziert`
(in der App mit `*`). Auch hier reicht dank Volume-Mount ein Browser-Reload.

## Tarife pflegen

Preise ändern sich. Alle Werte stehen in `tarife/*.yaml` mit Quelle und Stand.
Werte, die nicht von der offiziellen Seite bestätigt sind, stehen unter
`unverifiziert:` und werden in der App mit `*` markiert.
Nach einer Änderung: `pytest -q` laufen lassen – die Tests prüfen gegen die
Preisbeispiele auf scouter.de. Dank Volume-Mount reicht danach ein Browser-Reload
(Cache max. 5 Minuten).

### Offene Punkte (bewusst nicht geraten)

- scouter: Wochenpreise und Klasse-L-Tagespreis aus älteren Quellen, Nachttarif nicht modelliert
- scouter/Flinkster: Abrechnungstakt bei scouter und Haustierregeln beider Anbieter in den AGB prüfen
- Flinkster: Sa/So-Deckel nur, wenn die Buchung komplett an einem Sa oder So liegt;
  Freikilometer nur, wenn der Deckel tatsächlich greift (konservative Annahme)
- Einmalkosten (Registrierung, Jahres-Unfallschutz) sind nicht in den Fahrtpreisen enthalten

## Phase 2: automatischer Abruf

`fetchers/base.py` beschreibt die Schnittstelle. Grundregeln:
Abruf läuft in eigenem Container/Job, nie im Web-Request; Ergebnisse mit Zeitstempel
in SQLite cachen; die App fällt bei Fehlern auf die manuelle Eingabe zurück;
Uptime-Kuma-Push zur Überwachung. AGB der Vermieter beachten.
