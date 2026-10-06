"""Gemeinsames aller Seiten: Formatierung, Farben, Gestaltung, Tarife, Datenbank."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3

import streamlit as st

from engine import lade_tarife
from speicher.fahrten import db_pfad, oeffnen

TARIF_ORDNER = Path(__file__).parent.parent / "tarife"
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


@st.cache_data(ttl=300)
def tarife() -> dict:
    return lade_tarife(TARIF_ORDNER)


@st.cache_resource
def _verbindung() -> sqlite3.Connection:
    return oeffnen(db_pfad())


def verbindung() -> sqlite3.Connection | None:
    """Gemeinsame DB-Verbindung; bei Fehler None und eine Meldung mit Ursache (Fehler wird nicht gecacht)."""
    try:
        return _verbindung()
    except (OSError, sqlite3.Error) as fehler:
        st.error(f"Die Fahrten-Datenbank ist nicht erreichbar ({db_pfad()}): {fehler}")
        return None


def euro(betrag: float, stellen: int = 2) -> str:
    return f"{betrag:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def zahl(wert: float, stellen: int = 1) -> str:
    return f"{wert:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def zeitpunkt(dt: datetime) -> str:
    return f"{WOCHENTAGE[dt.weekday()]} {dt:%d.%m.}, {dt:%H:%M}"


# ---------- Gestaltung, die das Theme nicht abdeckt ----------

# Eigene Farben für die HTML-Blöcke; Werte passend zu [theme.light] / [theme.dark] in config.toml
PALETTEN = {
    "light": {"akzent": "#1F5C3A", "tinte": "#1C1B18", "text2": "#3F3C34", "leise": "#6B675C",
              "blass": "#9A9586", "linie": "#DAD5C8", "spur": "#ECE8DE"},
    "dark": {"akzent": "#7CC49A", "tinte": "#ECE9E1", "text2": "#CFCBC1", "leise": "#A39F94",
             "blass": "#77736A", "linie": "#3A3832", "spur": "#2C2B26"},
}
GRUPPENFARBEN = {
    "light": {"Carsharing": "#1F5C3A", "Mietwagen": "#2E4A7D", "Bahn": "#A4492A"},
    "dark": {"Carsharing": "#7CC49A", "Mietwagen": "#8FA8DA", "Bahn": "#E08B66"},
}


def modus() -> str:
    return "dark" if st.context.theme.type == "dark" else "light"


# Hell/Dunkel-Knopf. Streamlit hat dafür keine Python-Funktion; er setzt dieselbe Browser-Einstellung,
# die sonst das (hier ausgeblendete) Streamlit-Menü schreibt, und lädt neu. Das Symbol setzt das Skript,
# weil der Sanitizer SVG direkt im HTML entfernt; "<" im Skript muss maskiert sein, sonst läuft es nicht.
SONNE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">'
         '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2'
         'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')
MOND = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">'
        '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>')


def gestaltung() -> None:
    """CSS für die eigenen HTML-Blöcke und der Hell/Dunkel-Knopf; auf jeder Seite gleich."""
    m = modus()
    variablen = "".join(f"--{k}: {v};" for k, v in PALETTEN[m].items())
    st.html(f"""
    <style>
      :root {{ {variablen} }}
      header[data-testid="stHeader"] {{ background: transparent; }}
      /* Kopfleiste und Werkzeugleiste sind seitenbreit und schlucken sonst Klicks auf den Knopf;
         klickbar bleiben nur die Navigation (oben bzw. mobil der Menüknopf) */
      header[data-testid="stHeader"], header[data-testid="stHeader"] div {{ pointer-events: none; }}
      header[data-testid="stHeader"] :is(a, button) {{ pointer-events: auto; }}
      .block-container {{ padding-top: 2.5rem; padding-bottom: 4rem; max-width: 46rem; }}
      h1 {{ font-size: 2.6rem !important; line-height: 1.05 !important; letter-spacing: -0.01em; }}
      h1 em {{ color: var(--akzent); }}
      .unterzeile {{ color: var(--leise); margin: -0.6rem 0 0.4rem; }}

      .block-container {{ position: relative; }}
      [data-testid="stElementContainer"]:has(> .stHtml #modus-knopf),
      [data-testid="stElementContainer"]:has(#modus-knopf) {{ position: static; }}
      .modus {{ position: absolute; top: 1.1rem; right: 1rem; z-index: 10; width: 2.5rem; height: 2.5rem;
               display: grid; place-items: center; border-radius: 50%; cursor: pointer;
               background: transparent; color: var(--tinte); border: 1px solid var(--linie); }}
      .modus:hover {{ border-color: var(--leise); }}
      .modus svg {{ width: 1.15rem; height: 1.15rem; }}

      .eckdaten {{ display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem; color: var(--text2);
                  font-variant-numeric: tabular-nums; border-top: 1px solid var(--linie);
                  padding-top: 0.75rem; margin-top: 0.25rem; }}
      .eckdaten b {{ font-weight: 600; }}

      .sieger {{ border-top: 2px solid var(--tinte); padding: 1.1rem 0 0.4rem; margin-top: 0.5rem; }}
      .sieger .marke {{ font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--leise); }}
      .sieger .preis {{ font-family: instrument-serif, Georgia, serif; font-size: 3.6rem; line-height: 1;
                       margin: 0.35rem 0 0.2rem; font-variant-numeric: tabular-nums; }}
      .sieger .name {{ font-size: 1.15rem; font-weight: 600; }}
      .sieger .abstand {{ color: var(--akzent); margin-top: 0.3rem; }}

      .rang {{ list-style: none; padding: 0; margin: 1rem 0 0; }}
      .rang details {{ border-top: 1px solid var(--linie); }}
      .rang details:last-child {{ border-bottom: 1px solid var(--linie); }}
      .rang summary {{ list-style: none; cursor: pointer; padding: 0.8rem 0 0.7rem;
                      display: grid; grid-template-columns: 1.6rem 1fr auto; gap: 0 0.5rem; align-items: baseline; }}
      .rang summary::-webkit-details-marker {{ display: none; }}
      .rang .nr {{ color: var(--blass); font-variant-numeric: tabular-nums; }}
      .rang .wer b {{ font-weight: 600; }}
      .rang .wer span {{ color: var(--leise); }}
      .rang .betrag {{ font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }}
      .rang .balken {{ grid-column: 2 / 4; height: 4px; background: var(--spur); border-radius: 2px; margin-top: 0.45rem; }}
      .rang .balken i {{ display: block; height: 100%; border-radius: 2px; }}
      .rang .meta {{ grid-column: 2 / 4; font-size: 0.85rem; color: var(--leise); margin-top: 0.35rem; }}
      .rang .innen {{ padding: 0 0 1rem 2.1rem; font-size: 0.92rem; }}
      .rang .posten {{ display: grid; grid-template-columns: 1fr auto; gap: 0.15rem 1rem;
                      font-variant-numeric: tabular-nums; max-width: 22rem; }}
      .rang .posten span:nth-child(even) {{ text-align: right; }}
      .rang .innen ul {{ margin: 0.6rem 0 0; padding-left: 1.1rem; color: var(--text2); }}
      .fzeile {{ border-top: 1px solid var(--linie); padding: 0.8rem 0 0.5rem; margin-top: 0.4rem;
                display: grid; grid-template-columns: 3.2rem 1fr auto; gap: 0 0.5rem; align-items: baseline; }}
      .fzeile .datum {{ color: var(--blass); font-variant-numeric: tabular-nums; }}
      .fzeile .wer b {{ font-weight: 600; }}
      .fzeile .wer span {{ color: var(--leise); }}
      .fzeile .betrag {{ font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }}
      .fzeile .meta {{ grid-column: 2 / 4; font-size: 0.85rem; color: var(--leise); margin-top: 0.3rem; }}
      .fzeile .meta i {{ display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; margin-right: 0.35rem; }}
      .fzeile .marke {{ display: inline-block; border: 1px solid var(--linie); border-radius: 0.8rem;
                       padding: 0 0.5rem; margin-left: 0.35rem; font-size: 0.78rem; white-space: nowrap; }}
      .fzeile .marke.offen {{ border-color: var(--akzent); color: var(--akzent); font-weight: 600; }}
      .fuss {{ color: var(--blass); font-size: 0.8rem; margin-top: 2.5rem; }}
      .fuss a {{ color: inherit; }}
    </style>
    """)

    ziel = "Light" if m == "dark" else "Dark"
    st.html(f"""
    <button class="modus" id="modus-knopf" type="button"
            aria-label="{'Helles' if m == 'dark' else 'Dunkles'} Design" title="{'Helles' if m == 'dark' else 'Dunkles'} Design">
    </button>
    <script>
    {{
      const knopf = document.getElementById("modus-knopf");
      knopf.innerHTML = {json.dumps(SONNE if m == "dark" else MOND).replace("<", "\\u003c")};
      knopf.addEventListener("click", () => {{
        // Streamlit merkt sich das Design je Pfad der zuerst geladenen Seite – daher für alle Seiten setzen
        const basis = window.location.pathname.replace(/(fahrten|auswertung)\\/?$/, "");
        for (const seite of ["", "fahrten", "auswertung"]) {{
          try {{ localStorage.setItem(`stActiveTheme-${{basis}}${{seite}}-v2`, JSON.stringify("{ziel}")); }} catch (e) {{}}
        }}
        window.location.reload();
      }});
    }}
    </script>
    """, unsafe_allow_javascript=True)

