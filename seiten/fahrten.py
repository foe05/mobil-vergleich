"""Seite Fahrten: gespeicherte Entscheidungen, Kosten ohne Vergleich, Rechnung nachtragen."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time
from html import escape

import streamlit as st

from engine import Eintrag
from engine.eigenauto import MONATE
from seiten.gemeinsam import GRUPPENFARBEN, euro, modus, verbindung, zahl, zeitpunkt
from speicher.fahrten import aendern, alle, anlegen, loeschen

FARBEN = GRUPPENFARBEN[modus()]
ARTEN = ["Carsharing", "Mietwagen", "Bahn", "Sonstiges"]
EIGENAUTO = {"wäre gefahren": True, "nicht gefahren": False}


@st.dialog("Kosten ohne Vergleich eintragen")
def kosten_eintragen(con) -> None:
    heute = date.today()
    with st.container(horizontal=True, gap="small"):
        sd = st.date_input("Abholung", value=heute, format="DD.MM.YYYY", key="neu_sd")
        stt = st.time_input("um", value=time(10), step=900, key="neu_st")
    with st.container(horizontal=True, gap="small"):
        ed = st.date_input("Rückgabe", value=heute, format="DD.MM.YYYY", key="neu_ed")
        et = st.time_input("um ", value=time(12), step=900, key="neu_et")
    anlass = st.text_input("Anlass", key="neu_anlass")
    art = st.pills("Art", ARTEN, default="Sonstiges", key="neu_art")
    anbieter = st.text_input("Anbieter", key="neu_anbieter", placeholder="z. B. Taxi Kassel")
    with st.container(horizontal=True, gap="small"):
        km = st.number_input("Kilometer", min_value=0.0, step=10.0, key="neu_km")
        betrag = st.number_input("Betrag €", min_value=0.0, step=5.0, format="%.2f", key="neu_betrag")
    eigen = st.segmented_control("Mit eigenem Auto?", list(EIGENAUTO), key="neu_eigen")

    if st.button("Speichern", type="primary", key="neu_speichern"):
        start, ende = datetime.combine(sd, stt), datetime.combine(ed, et)
        if ende <= start:
            st.error("Die Rückgabe muss nach der Abholung liegen.")
        elif not anlass.strip() or not anbieter.strip():
            st.error("Bitte Anlass und Anbieter angeben.")
        elif eigen is None:
            st.error("Bitte wählen, ob ihr mit dem eigenen Auto gefahren wärt.")
        elif art is None:
            st.error("Bitte eine Art wählen.")
        else:
            try:
                anlegen(con, Eintrag(start=start, ende=ende, anlass=anlass.strip(), ergebnis=anbieter.strip(),
                                     gruppe=art, km_geplant=km, preis_geplant=betrag,
                                     eigenauto_gefahren=EIGENAUTO[eigen],
                                     km_tatsaechlich=km, preis_tatsaechlich=betrag))
            except Exception as fehler:
                st.error(f"Speichern fehlgeschlagen: {fehler}")
            else:
                for k in [k for k in st.session_state if k.startswith("neu_")]:
                    del st.session_state[k]
                st.rerun()


def zeile(e: Eintrag, jetzt: datetime) -> str:
    marken = []
    if e.rechnung_offen(jetzt):
        marken.append('<span class="marke offen">Rechnung offen</span>')
    marken.append(f'<span class="marke">mit Auto: {"ja" if e.eigenauto_gefahren else "nein"}</span>')
    farbe = FARBEN.get(e.gruppe, "#6B675C")
    betrag = euro(e.preis) if e.gefahren else "–"
    return f"""
<div class="fzeile">
  <span class="datum">{e.start:%d.%m.}</span>
  <span class="wer"><b>{escape(e.anlass)}</b> <span>{escape(e.ergebnis)}</span></span>
  <span class="betrag">{betrag}</span>
  <span class="meta"><i style="background:{farbe}"></i>{escape(e.gruppe)} · {zeitpunkt(e.start)} bis {zeitpunkt(e.ende)} · {zahl(e.km, 0)} km {"".join(marken)}</span>
</div>"""


def rangliste(e: Eintrag) -> str:
    rang = (e.vergleich or {}).get("rangliste") or []
    if not rang:
        return ""
    hoechster = max(r["gesamt"] for r in rang) or 1
    zeilen = []
    for i, r in enumerate(rang, 1):
        posten = "".join(f"<span>{escape(k)}</span><span>{euro(v)}</span>" for k, v in r["posten"].items() if v)
        zeilen.append(f"""
<details>
  <summary>
    <span class="nr">{i}</span>
    <span class="wer"><b>{escape(r["anbieter"])}</b> <span>{escape(r["option"])}</span></span>
    <span class="betrag">{euro(r["gesamt"])}</span>
    <span class="balken"><i style="width:{r["gesamt"] / hoechster * 100:.1f}%;background:{FARBEN.get(r["gruppe"], '#6B675C')}"></i></span>
  </summary>
  <div class="innen"><div class="posten">{posten}</div></div>
</details>""")
    stand = ", ".join(f"{k}: {v}" for k, v in (e.vergleich.get("tarifstand") or {}).items())
    return (f'<div class="rang">{"".join(zeilen)}</div>'
            f'<p class="fuss" style="margin-top:0.6rem">Tarifstand damals – {escape(stand)}</p>')


def details(con, e: Eintrag) -> None:
    with st.expander("Nachtragen, Vergleich, Löschen", key=f"ex_{e.id}"):
        with st.container(horizontal=True, gap="small"):
            preis = st.number_input("Tatsächlicher Preis €", min_value=0.0, step=1.0, format="%.2f",
                                    value=float(e.preis), key=f"preis_{e.id}")
            km = st.number_input("Tatsächliche km", min_value=0.0, step=10.0,
                                 value=float(e.km), key=f"km_{e.id}")
        if st.button("Nachtragen", key=f"nachtragen_{e.id}"):
            try:
                aendern(con, replace(e, preis_tatsaechlich=preis, km_tatsaechlich=km))
            except Exception as fehler:
                st.error(f"Speichern fehlgeschlagen: {fehler}")
            else:
                st.rerun()
        html = rangliste(e)
        if html:
            st.markdown("**Damaliger Vergleich**")
            st.html(html)
        st.divider()
        sicher = st.checkbox("Diesen Eintrag wirklich löschen", key=f"sicher_{e.id}")
        if st.button("Löschen", key=f"loeschen_{e.id}", disabled=not sicher, icon=":material/delete:"):
            try:
                loeschen(con, e.id)
            except Exception as fehler:
                st.error(f"Löschen fehlgeschlagen: {fehler}")
            else:
                st.rerun()


st.title("Fahrten", anchor=False)
con = verbindung()
if con is None:
    st.stop()

if st.button("Kosten ohne Vergleich eintragen", icon=":material/add:"):
    kosten_eintragen(con)

eintraege = alle(con)
if not eintraege:
    st.info("Noch keine Fahrten gespeichert.")
    st.stop()

jetzt = datetime.now()
monat = None
for e in eintraege:
    if (e.start.year, e.start.month) != monat:
        monat = (e.start.year, e.start.month)
        st.subheader(f"{MONATE[monat[1] - 1]} {monat[0]}", anchor=False)
    st.html(zeile(e, jetzt))
    details(con, e)
