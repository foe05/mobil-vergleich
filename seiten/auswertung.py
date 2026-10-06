"""Seite Auswertung: Hätte sich ein eigenes Auto gelohnt – ab wann, und was müsste sich ändern?"""
from __future__ import annotations

from datetime import date, datetime
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from engine import BreakEven, Profil, break_even, verlauf, zeitraeume, zeitraumkosten
from seiten.gemeinsam import PALETTEN, euro, modus, tarife, verbindung, zahl
from speicher.fahrten import alle

ARTEN = {"Monat": "monat", "Quartal": "quartal", "Jahr": "jahr", "Gesamt": "gesamt"}
# Linienfarben je Profil (feste Reihenfolge der Profile, nie nach Rang); mit dem dataviz-Validator
# geprüft: Helligkeitsband, Sättigung, Farbsehschwäche, Kontrast zum Hintergrund – je Modus.
# "Heute" ist keine Kategorie, sondern der Maßstab und läuft in Tintenfarbe.
PROFILFARBEN = {
    "light": ["#1A6E40", "#3D63C2", "#BF7A22"],
    "dark": ["#237A48", "#6E8FE6", "#C0842A"],
}
HINTERGRUND = {"light": "#F6F4EE", "dark": "#161613"}   # wie backgroundColor in config.toml
M = modus()
TINTE = PALETTEN[M]["tinte"]


def name_mit_stern(p: Profil) -> str:
    return p.name + ("*" if p.unverifiziert else "")


def im(zr) -> str:
    """Zeitangabe für den Kernsatz: „im Q4 2026“, „im Jahr 2026“, „insgesamt“."""
    if zr.art == "jahr":
        return f"im Jahr {zr.label}"
    if zr.art == "gesamt":
        return "insgesamt"
    return f"im {zr.label}"


def datum_de(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def vorzeichen(betrag: float) -> str:
    if betrag > 0:
        return "+" + euro(betrag)
    if betrag < 0:
        return "−" + euro(-betrag)
    return euro(0)


def break_even_satz(p: Profil, be: BreakEven) -> str:
    if be.status == "schwelle":
        fahrten = "weitere Fahrt" if be.weitere_fahrten == 1 else "weitere Fahrten"
        return (f"{p.name} lohnt sich ab ca. {zahl(be.schwelle_km, 0)} km/Jahr. "
                f"Ihr kommt {'hochgerechnet ' if be.hochgerechnet else ''}auf {zahl(be.km_jahr, 0)} km – "
                f"etwa {be.weitere_fahrten} {fahrten} wie ‚{be.anlass}‘ pro Jahr.")
    if be.status == "bereits":
        return f"{p.name} hätte sich in den letzten 12 Monaten schon gelohnt."
    if be.status == "nie":
        return (f"{p.name} lohnt sich mit eurem Fahrprofil nicht – schon die km-Kosten liegen über "
                f"eurem heutigen Preis pro km.")
    return "Für eine Schwelle braucht es mindestens drei Fahrten, die ihr mit eigenem Auto gemacht hättet."


def verlaufsdiagramm(eintraege, profile: list[Profil], farben: dict[str, str], heute: date) -> alt.LayerChart:
    df = pd.DataFrame(verlauf(eintraege, profile, heute))
    df["datum"] = pd.to_datetime(df["datum"])
    reihen = ["Heute"] + [p.name for p in profile]

    # Breite Tabelle für den Tooltip: alle Reihen eines Tages auf einen Blick
    breit = df.pivot(index="datum", columns="reihe", values="kumuliert")[reihen].reset_index()
    for r in reihen:
        breit[r] = breit[r].map(euro)
    breit["Tag"] = breit["datum"].dt.strftime("%d.%m.%Y")

    spanne = (df["datum"].max() - df["datum"].min()).days
    if spanne <= 62:
        x_achse = alt.Axis(title=None, format="%d.%m.", labelAngle=0, tickCount=6, grid=False)
    else:
        kurz = "['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez']"
        x_achse = alt.Axis(title=None, labelAngle=0, tickCount={"interval": "month", "step": 1}, grid=False,
                           labelExpr=f"{kurz}[month(datum.value)] + (month(datum.value) == 0 ? ' ' + "
                                     f"timeFormat(datum.value, '%y') : '')")
    y_achse = alt.Axis(title=None, tickCount=5, domain=False, ticks=False,
                       labelExpr="replace(format(datum.value, ',.0f'), ',', '.') + ' €'")
    farbe = alt.Color("reihe:N", scale=alt.Scale(domain=reihen, range=[farben[r] for r in reihen]), legend=None)
    x = alt.X("datum:T", axis=x_achse)
    y = alt.Y("kumuliert:Q", axis=y_achse)

    basis = alt.Chart(df)
    linien_profile = basis.transform_filter(alt.datum.reihe != "Heute").mark_line(strokeWidth=2).encode(x, y, farbe)
    linie_heute = basis.transform_filter(alt.datum.reihe == "Heute").mark_line(
        strokeWidth=3, interpolate="step-after").encode(x, y, farbe)

    zeiger = alt.selection_point(nearest=True, on="pointermove", fields=["datum"], empty=False, clear="pointerout")
    regel = alt.Chart(breit).mark_rule(color=PALETTEN[M]["blass"], strokeWidth=1).encode(
        x="datum:T",
        opacity=alt.condition(zeiger, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("Tag:N")] + [alt.Tooltip(f"{r}:N", title=r) for r in reihen],
    ).add_params(zeiger)
    punkte = basis.mark_point(filled=True, size=70, stroke=HINTERGRUND[M],
                              strokeWidth=2, opacity=1).encode(
        x, y, farbe).transform_filter(zeiger)
    return (alt.layer(linien_profile, linie_heute, regel, punkte)
            .properties(height=280)
            .configure_view(stroke=None))


st.html("""
<style>
  .sieger .kernsatz { font-family: instrument-serif, Georgia, serif; font-size: 2.1rem; line-height: 1.15;
                      margin: 0.4rem 0 0.3rem; font-variant-numeric: tabular-nums; }
  .sieger .kernsatz b { font-weight: 400; color: var(--akzent); }
  .sieger .stand { color: var(--leise); }
  .rang .satz { grid-column: 2 / 4; color: var(--text2); margin-top: 0.4rem; font-size: 0.95rem; }
  .rang .meta i, .legende i { display: inline-block; width: 0.9rem; height: 3px; border-radius: 2px;
                              vertical-align: middle; margin-right: 0.4rem; }
  .legende { display: flex; flex-wrap: wrap; gap: 0.2rem 1.1rem; color: var(--text2); font-size: 0.9rem;
             margin: 0.2rem 0 1.6rem; }
  .legende .heute i { height: 4px; }
  .fuss p { margin: 0 0 0.45rem; }
</style>
""")

st.title("Auswertung", anchor=False)
con = verbindung()
if con is None:
    st.stop()

T = tarife()
profile: list[Profil] = T["eigenauto"]
eintraege = alle(con)
if not eintraege:
    st.info("Noch keine Fahrten gespeichert.")
    st.stop()
if not profile:
    st.warning("Es sind keine Profile für ein eigenes Auto geladen.")
    for h in T["hinweise"]:
        st.caption(h)
    st.stop()

heute = date.today()

# ---------- Zeitraum ----------

with st.container(horizontal=True, gap="small", vertical_alignment="bottom"):
    wahl = st.segmented_control("Zeitraum", list(ARTEN), default="Quartal", key="zr_art")
    art = ARTEN.get(wahl or "Quartal")
    liste = zeitraeume(art, eintraege, heute) or zeitraeume("gesamt", eintraege, heute)
    label = st.selectbox("Welcher", [z.label for z in liste], key=f"zr_{art}", label_visibility="collapsed")
    zr = next(z for z in liste if z.label == label)

# ---------- Kernsatz ----------

kosten = {p.id: zeitraumkosten(eintraege, p, zr) for p in profile}
reihenfolge = sorted(profile, key=lambda p: kosten[p.id].differenz)
bestes = reihenfolge[0]
d = kosten[bestes.id].differenz
if d == 0:
    aussage = "genauso viel"
else:
    aussage = f"<b>{euro(abs(d))}</b> {'mehr' if d > 0 else 'weniger'}"
st.html(f"""
<div class="sieger">
  <div class="marke">{escape(zr.label)} · mit eigenem Auto</div>
  <div class="kernsatz">Ein {escape(name_mit_stern(bestes))} hätte euch {escape(im(zr))} {aussage} gekostet.</div>
  <div class="stand">Heute {euro(kosten[bestes.id].ist)} · mit Profil {euro(kosten[bestes.id].mit_profil)}</div>
</div>
""")

# ---------- Profile ----------

farben = {"Heute": TINTE} | {p.name: PROFILFARBEN[M][i % len(PROFILFARBEN[M])] for i, p in enumerate(profile)}
zeilen = []
for i, p in enumerate(reihenfolge, 1):
    k = kosten[p.id]
    posten = "".join(f"<span>{escape(n)}</span><span>{euro(v)}/Jahr</span>" for n, v in p.fix_pro_jahr.items() if v)
    posten += "".join(f"<span>{escape(n)}</span><span>{euro(v, 3)}/km</span>"
                      for n, v in p.variabel_pro_km.items() if v)
    zeilen.append(f"""
<details>
  <summary>
    <span class="nr">{i}</span>
    <span class="wer"><b>{escape(name_mit_stern(p))}</b></span>
    <span class="betrag">{vorzeichen(k.differenz)}</span>
    <span class="meta"><i style="background:{farben[p.name]}"></i>heute {euro(k.ist)} · mit Profil {euro(k.mit_profil)}</span>
    <span class="satz">{escape(break_even_satz(p, break_even(eintraege, p, heute)))}</span>
  </summary>
  <div class="innen"><div class="posten">{posten}</div></div>
</details>""")
st.html(f'<div class="rang">{"".join(zeilen)}</div>')

# ---------- Verlauf ----------

st.subheader("Verlauf", anchor=False)
st.caption("Kosten kumuliert seit der ersten Fahrt – heute gegen jedes Profil.")
st.html('<div class="legende">' + "".join(
    f'<span class="{"heute" if r == "Heute" else ""}"><i style="background:{f}"></i>{escape(r)}</span>'
    for r, f in farben.items()) + "</div>")
st.altair_chart(verlaufsdiagramm(eintraege, profile, farben, heute), width="stretch",
                alt="Kumulierte Kosten seit der ersten Fahrt: heute gegen jedes Profil")

# ---------- Annahmen und Stand ----------

offen = sum(e.rechnung_offen(datetime.now()) for e in eintraege)
fuss = [
    "Annahmen: Fixkosten zählen anteilig je Tag, ein laufender Zeitraum nur bis heute. Für die Schwelle "
    "kosten zusätzliche km heute denselben Durchschnittspreis pro km wie eure bisherigen Fahrten, "
    "die ihr mit eigenem Auto gemacht hättet (letzte 12 Monate).",
    "Profilstand: " + " · ".join(
        f'{escape(p.name)}, Stand {escape(datum_de(p.stand))}, <a href="{escape(p.quelle)}" target="_blank">Quelle</a>'
        for p in profile),
]
if any(p.unverifiziert for p in profile):
    fuss.append("* enthält geschätzte, nicht belegte Werte: " + " · ".join(
        f"{escape(p.name)} ({escape(', '.join(p.unverifiziert))})" for p in profile if p.unverifiziert))
fuss.append("Keine offenen Rechnungen." if not offen else
            f"{offen} {'Fahrt' if offen == 1 else 'Fahrten'} mit offener Rechnung – dort zählt der geplante Preis.")
fuss += [escape(h) for h in T["hinweise"]]
st.html('<div class="fuss">' + "".join(f"<p>{z}</p>" for z in fuss) + "</div>")
