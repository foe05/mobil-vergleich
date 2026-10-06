"""Wie fahren wir? – Mobilitäts-Vergleich für Familie mit Hund (Kassel)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from engine import BahnAngebot, MietAngebot, Szenario, lade_tarife, vergleiche

TARIF_ORDNER = Path(__file__).parent / "tarife"
FARBEN = {"Carsharing": "#1F5C3A", "Mietwagen": "#1F3864", "Bahn": "#8A3B12"}

st.set_page_config(page_title="Wie fahren wir?", page_icon="🚗", layout="wide")


@st.cache_data(ttl=300)
def tarife() -> dict:
    return lade_tarife(TARIF_ORDNER)


# ---------- Voreinstellungen ----------

def naechster(wochentag: int) -> date:
    heute = date.today()
    return heute + timedelta(days=(wochentag - heute.weekday()) % 7 or 7)


def voreinstellungen() -> dict:
    sa, fr = naechster(5), naechster(4)
    return {
        "IKEA-Nachmittag": (sa, time(13), sa, time(17), 30),
        "Oma (1 Nacht)": (sa, time(10), sa + timedelta(days=1), time(16), 100),
        "Langes Wochenende": (fr, time(14), fr + timedelta(days=3), time(18), 700),
        "Urlaub (2 Wochen)": (sa, time(8), sa + timedelta(days=14), time(18), 1500),
    }


def setze_voreinstellung():
    wahl = st.session_state["preset"]
    if wahl in voreinstellungen():
        sd, stt, ed, et, km = voreinstellungen()[wahl]
        st.session_state.update(start_d=sd, start_t=stt, ende_d=ed, ende_t=et, km=km)


if "start_d" not in st.session_state:
    st.session_state["preset"] = "Oma (1 Nacht)"
    setze_voreinstellung()

# ---------- Eingaben ----------

st.title("Wie fahren wir?")
st.radio("Reise", [*voreinstellungen().keys(), "Eigene Eingabe"], key="preset",
         horizontal=True, on_change=setze_voreinstellung)

c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
c1.date_input("Abholung", key="start_d", format="DD.MM.YYYY")
c2.time_input("um", key="start_t", step=900)
c3.date_input("Rückgabe", key="ende_d", format="DD.MM.YYYY")
c4.time_input("um ", key="ende_t", step=900)
c5.number_input("Kilometer gesamt", min_value=0, step=10, key="km")

with st.expander("Einstellungen", expanded=False):
    e1, e2, e3, e4 = st.columns(4)
    hund = e1.checkbox("Hund fährt mit", value=True)
    spritpreis = e2.number_input("Spritpreis €/l", value=1.75, step=0.05, format="%.2f")
    km_paket = e3.checkbox("scouter 500-km-Paket nutzen", value=True,
                           help="Restkilometer verfallen nicht – lohnt sich bei regelmäßiger Nutzung.")
    sb = e4.checkbox("Flinkster Selbstbehalt reduzieren", value=False)

start = datetime.combine(st.session_state["start_d"], st.session_state["start_t"])
ende = datetime.combine(st.session_state["ende_d"], st.session_state["ende_t"])
if ende <= start:
    st.error("Die Rückgabe liegt vor der Abholung. Bitte Datum oder Uhrzeit der Rückgabe korrigieren.")
    st.stop()

sz = Szenario(start=start, ende=ende, km=float(st.session_state["km"]), spritpreis=spritpreis,
              hund=hund, km_paket_nutzen=km_paket, selbstbehalt_reduzieren=sb)
st.caption(f"Dauer: {sz.stunden:.1f} h ({sz.stunden / 24:.1f} Tage) · {sz.km:.0f} km")

# ---------- Angebote ohne Tariftabelle ----------

T = tarife()
miet: list[MietAngebot] = []
with st.expander("Angebote für diese Reise eintragen (Sixt, Europcar, Getaround, Bahn)", expanded=False):
    st.caption("Preis bei 0 lassen, wenn kein Angebot vorliegt – die Option erscheint dann nicht im Vergleich.")
    for m in T["angebote"].get("mietwagen", []):
        st.markdown(f"**{m['name']}** · [Suche öffnen]({m['link']})")
        a1, a2, a3, a4, a5 = st.columns(5)
        preis = a1.number_input("Preis gesamt €", min_value=0.0, step=5.0, key=f"{m['id']}_preis")
        frei = a2.number_input("Frei-km (0 = unbegrenzt)", min_value=0, step=50, key=f"{m['id']}_frei")
        mehr = a3.number_input("Mehr-km €/km", min_value=0.0, step=0.05, format="%.2f", key=f"{m['id']}_mehr")
        verbr = a4.number_input("Verbrauch l/100 km", min_value=0.0, step=0.5,
                                value=float(m.get("verbrauch_l_100km", 6.5)), key=f"{m['id']}_verbr")
        extras = a5.number_input("Extras €", min_value=0.0, step=5.0, key=f"{m['id']}_extras",
                                 help="z. B. Reinigungspauschale wegen Hund, Zusatzfahrer")
        miet.append(MietAngebot(m["id"], m["name"], preis, frei, mehr, verbr, extras, m.get("haustiere", "pruefen")))

    b = T["angebote"].get("bahn", {})
    st.markdown(f"**Bahn** · [Suche öffnen]({b.get('link', 'https://www.bahn.de')})")
    b1, b2 = st.columns(2)
    bahn_preis = b1.number_input("Tickets gesamt € (Familie + Hund, hin & zurück)", min_value=0.0, step=5.0)
    bahn_vor_ort = b2.number_input("Mobilität am Ziel €", min_value=0.0, step=5.0)
    bahn = BahnAngebot(bahn_preis, bahn_vor_ort, b.get("haustiere", "ja"))

# ---------- Ergebnis ----------

ergebnisse = vergleiche(T, sz, miet, bahn)
if not ergebnisse:
    st.info("Keine Option passt. Trag oben ein Angebot ein oder prüf die Einstellungen.")
    st.stop()

beste = ergebnisse[0]
st.subheader(f"Günstigste Option: {beste.anbieter} – {beste.option}: {beste.gesamt:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))

df = pd.DataFrame([{
    "Option": f"{e.anbieter} – {e.option}" + (" *" if e.unsicher else ""),
    "Gruppe": e.gruppe,
    "Gesamt": e.gesamt,
    "Label": f"{e.gesamt:,.0f} €".replace(",", "."),
} for e in ergebnisse])

basis = alt.Chart(df).encode(
    y=alt.Y("Option:N", sort=None, title=None, axis=alt.Axis(labelLimit=320, labelColor="#111111", labelFontSize=13)),
    x=alt.X("Gesamt:Q", title="Kosten (€)", axis=alt.Axis(labelColor="#111111", titleColor="#111111")),
)
balken = basis.mark_bar().encode(
    color=alt.Color("Gruppe:N", scale=alt.Scale(domain=list(FARBEN), range=list(FARBEN.values())),
                    legend=alt.Legend(orient="bottom", title=None, labelColor="#111111")),
    tooltip=["Option", "Gruppe", alt.Tooltip("Gesamt:Q", format=",.2f")],
)
text = basis.mark_text(align="left", dx=4, color="#111111", fontSize=13).encode(text="Label:N")
st.altair_chart((balken + text).properties(height=max(160, 44 * len(df))), width="stretch")
if any(e.unsicher for e in ergebnisse):
    st.caption("* enthält nicht verifizierte Tarifwerte – Details unten.")

# Aufschlüsselung
st.markdown("#### Aufschlüsselung")
zeilen = []
for e in ergebnisse:
    z = {"Option": f"{e.anbieter} – {e.option}", "Gesamt €": e.gesamt}
    z.update({f"{k} €": v for k, v in e.posten.items()})
    z["Hund"] = {"ja": "erlaubt", "nein": "nicht erlaubt", "pruefen": "Regel prüfen"}.get(e.haustiere, e.haustiere)
    zeilen.append(z)
st.dataframe(pd.DataFrame(zeilen).fillna(0), hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%.2f") for c in pd.DataFrame(zeilen).columns if c.endswith("€")})

with st.expander("Hinweise und Annahmen je Option"):
    for e in ergebnisse:
        st.markdown(f"**{e.anbieter} – {e.option}**")
        for h in e.hinweise:
            st.markdown(f"- {h}")
    st.markdown("---")
    for t in T["carsharing"]:
        st.caption(f"{t['name']}: Tarifstand {t['stand']} · Quelle: {t['quelle']}")
