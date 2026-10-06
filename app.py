"""Wie fahren wir? – Mobilitäts-Vergleich für Familie mit Hund (Kassel)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode

import streamlit as st

from engine import BahnAngebot, MietAngebot, Szenario, lade_tarife, vergleiche

TARIF_ORDNER = Path(__file__).parent / "tarife"
HUND = {"ja": "Hund erlaubt", "nein": "Hund nicht erlaubt", "pruefen": "Hunderegel prüfen"}
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

st.set_page_config(page_title="Wie fahren wir?", page_icon=":material/directions_car:", layout="centered")


@st.cache_data(ttl=300)
def tarife() -> dict:
    return lade_tarife(TARIF_ORDNER)


def euro(betrag: float, stellen: int = 2) -> str:
    return f"{betrag:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def zahl(wert: float, stellen: int = 1) -> str:
    return f"{wert:.{stellen}f}".replace(".", ",")


def zeitpunkt(dt: datetime) -> str:
    return f"{WOCHENTAGE[dt.weekday()]} {dt:%d.%m.}, {dt:%H:%M}"


def suchlink(anbieter: dict, start: datetime, ende: datetime) -> str:
    """Suchseite des Anbieters mit Ort und Reisezeit vorbelegt; ohne `suche` in angebote.yaml die Startseite."""
    s = anbieter.get("suche")
    if not s:
        return anbieter["link"]
    if anbieter["id"] == "sixt":
        return "https://www.sixt.de/betafunnel/#/offerlist?" + urlencode({
            "zen_pu_branch_id": s["filiale"], "zen_do_branch_id": s["filiale"],
            "zen_pu_title": s["titel"], "zen_do_title": s["titel"],
            "zen_pu_time": f"{start:%Y-%m-%dT%H:%M}", "zen_do_time": f"{ende:%Y-%m-%dT%H:%M}",
            "zen_vehicle_type": "car"})
    if anbieter["id"] == "europcar":
        return "https://www.europcar.de/de-de/reservation/vehicles?" + urlencode({
            "pickupLocation": s["station"], "dropoffLocation": s["station"],
            "pickupYear": start.year, "pickupMonth": start.month, "pickupDay": start.day,
            "pickupHour": start.hour, "pickupMinute": start.minute,
            "dropoffYear": ende.year, "dropoffMonth": ende.month, "dropoffDay": ende.day,
            "dropoffHour": ende.hour, "dropoffMinute": ende.minute})
    if anbieter["id"] == "getaround":
        return "https://getaround.com/de/search?" + urlencode({
            "address": s["adresse"], "city_display_name": s["adresse"], "country_scope": "DE",
            "latitude": s["breite"], "longitude": s["laenge"],
            "start_date": f"{start:%Y-%m-%d}", "start_time": f"{start:%H:%M}",
            "end_date": f"{ende:%Y-%m-%d}", "end_time": f"{ende:%H:%M}"})
    if anbieter["id"] == "bahn":
        # sts=false: nur die Suchmaske füllen – ohne Ziel würde die Suche sofort ins Leere laufen
        return "https://www.bahn.de/buchung/start#" + urlencode({
            "sts": "false", "so": s["start"], "soid": f"O={s['start']}",
            "hd": f"{start:%Y-%m-%dT%H:%M:%S}", "hza": "D",
            "rd": f"{ende:%Y-%m-%dT%H:%M:%S}", "rza": "D"},
            quote_via=lambda wert, *_: quote(wert, safe=":"))   # Uhrzeiten wie von bahn.de selbst erzeugt
    return anbieter["link"]


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
modus = "dark" if st.context.theme.type == "dark" else "light"
FARBEN = GRUPPENFARBEN[modus]
variablen = "".join(f"--{k}: {v};" for k, v in PALETTEN[modus].items())

st.html(f"""
<style>
  :root {{ {variablen} }}
  header[data-testid="stHeader"] {{ background: transparent; pointer-events: none; }}   /* sonst schluckt er Klicks auf den Knopf */
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
  .fuss {{ color: var(--blass); font-size: 0.8rem; margin-top: 2.5rem; }}
  .fuss a {{ color: inherit; }}
</style>
""")

# Hell/Dunkel-Knopf. Streamlit hat dafür keine Python-Funktion; er setzt dieselbe Browser-Einstellung,
# die sonst das (hier ausgeblendete) Streamlit-Menü schreibt, und lädt neu. Das Symbol setzt das Skript,
# weil der Sanitizer SVG direkt im HTML entfernt; "<" im Skript muss maskiert sein, sonst läuft es nicht.
SONNE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">'
         '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2'
         'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')
MOND = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round">'
        '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>')
ziel = "Light" if modus == "dark" else "Dark"
st.html(f"""
<button class="modus" id="modus-knopf" type="button"
        aria-label="{'Helles' if modus == 'dark' else 'Dunkles'} Design" title="{'Helles' if modus == 'dark' else 'Dunkles'} Design">
</button>
<script>
{{
  const knopf = document.getElementById("modus-knopf");
  knopf.innerHTML = {json.dumps(SONNE if modus == "dark" else MOND).replace("<", "\\u003c")};
  knopf.addEventListener("click", () => {{
    try {{ localStorage.setItem(`stActiveTheme-${{window.location.pathname}}-v2`, JSON.stringify("{ziel}")); }} catch (e) {{}}
    window.location.reload();
  }});
}}
</script>
""", unsafe_allow_javascript=True)


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


def eigene_eingabe():
    st.session_state["preset"] = None   # Hand-Änderung hebt die Auswahl auf


if "start_d" not in st.session_state:
    st.session_state["preset"] = "Oma (1 Nacht)"
    setze_voreinstellung()

# ---------- Eingaben ----------

st.title("Wie *fahren* wir?")
st.html('<p class="unterzeile">Carsharing, Mietwagen oder Bahn – für vier Personen und Hund ab Kassel.</p>')

st.pills("Reise", list(voreinstellungen()), key="preset", on_change=setze_voreinstellung,
         label_visibility="collapsed")

with st.container(horizontal=True, gap="small"):
    st.date_input("Abholung", key="start_d", format="DD.MM.YYYY", on_change=eigene_eingabe)
    st.time_input("um", key="start_t", step=900, on_change=eigene_eingabe)
with st.container(horizontal=True, gap="small"):
    st.date_input("Rückgabe", key="ende_d", format="DD.MM.YYYY", on_change=eigene_eingabe)
    st.time_input("um ", key="ende_t", step=900, on_change=eigene_eingabe)
st.number_input("Kilometer gesamt", min_value=0, step=10, key="km", on_change=eigene_eingabe)

with st.expander("Annahmen"):
    hund = st.toggle("Hund fährt mit", value=True)
    km_paket = st.toggle("scouter 500-km-Paket nutzen", value=True,
                         help="Restkilometer verfallen nicht – lohnt sich bei regelmäßiger Nutzung.")
    sb = st.toggle("Flinkster Selbstbehalt reduzieren", value=False)
    spritpreis = st.number_input("Spritpreis €/l", value=1.75, step=0.05, format="%.2f")

start = datetime.combine(st.session_state["start_d"], st.session_state["start_t"])
ende = datetime.combine(st.session_state["ende_d"], st.session_state["ende_t"])
if ende <= start:
    st.error("Die Rückgabe liegt vor der Abholung. Bitte Datum oder Uhrzeit der Rückgabe korrigieren.")
    st.stop()

sz = Szenario(start=start, ende=ende, km=float(st.session_state["km"]), spritpreis=spritpreis,
              hund=hund, km_paket_nutzen=km_paket, selbstbehalt_reduzieren=sb)
dauer = f"{zahl(sz.stunden)} h" if sz.stunden < 48 else f"{zahl(sz.stunden / 24)} Tage"
st.html(f'<div class="eckdaten"><span><b>{zeitpunkt(start)}</b> bis <b>{zeitpunkt(ende)}</b></span>'
        f'<span>{dauer}</span><span>{zahl(sz.km, 0)} km</span></div>')

# ---------- Angebote ohne Tariftabelle ----------

T = tarife()
miet: list[MietAngebot] = []
mietwagen = T["angebote"].get("mietwagen", [])
b = T["angebote"].get("bahn", {})

with st.expander("Angebote eintragen – Sixt, Europcar, Getaround, Bahn"):
    st.caption("Ohne Preis erscheint die Option nicht im Vergleich.")
    reiter = st.tabs([m["name"] for m in mietwagen] + ["Bahn"])
    for tab, m in zip(reiter, mietwagen):
        with tab:
            st.link_button(f"{m['name']} für diese Reise öffnen", suchlink(m, start, ende),
                           icon=":material/open_in_new:")
            preis = st.number_input("Preis gesamt €", min_value=0.0, step=5.0, key=f"{m['id']}_preis")
            with st.container(horizontal=True, gap="small"):
                frei = st.number_input("Frei-km", min_value=0, step=50, key=f"{m['id']}_frei",
                                       help="0 = unbegrenzt")
                mehr = st.number_input("Mehr-km €/km", min_value=0.0, step=0.05, format="%.2f",
                                       key=f"{m['id']}_mehr")
            with st.container(horizontal=True, gap="small"):
                verbr = st.number_input("l/100 km", min_value=0.0, step=0.5,
                                        value=float(m.get("verbrauch_l_100km", 6.5)), key=f"{m['id']}_verbr")
                extras = st.number_input("Extras €", min_value=0.0, step=5.0, key=f"{m['id']}_extras",
                                         help="z. B. Reinigungspauschale wegen Hund, Zusatzfahrer")
            miet.append(MietAngebot(m["id"], m["name"], preis, frei, mehr, verbr, extras,
                                    m.get("haustiere", "pruefen")))
    with reiter[-1]:
        st.link_button("Bahn für diese Reise öffnen", suchlink({"link": "https://www.bahn.de", **b}, start, ende),
                       icon=":material/open_in_new:")
        st.caption("Start und Reisezeit sind vorbelegt – Ziel und Reisende auf bahn.de ergänzen.")
        bahn_preis = st.number_input("Tickets gesamt € – Familie und Hund, hin und zurück",
                                     min_value=0.0, step=5.0)
        bahn_vor_ort = st.number_input("Mobilität am Ziel €", min_value=0.0, step=5.0)
    bahn = BahnAngebot(bahn_preis, bahn_vor_ort, b.get("haustiere", "ja"))

# ---------- Ergebnis ----------

ergebnisse = vergleiche(T, sz, miet, bahn)
if not ergebnisse:
    st.info("Keine Option passt. Trag oben ein Angebot ein oder prüf die Annahmen.")
    st.stop()

beste = ergebnisse[0]
abstand = ""
andere = [e for e in ergebnisse if e.anbieter != beste.anbieter]   # Vergleich mit dem nächsten Anbieter, nicht der nächsten Klasse
if andere:
    abstand = (f'<div class="abstand">{euro(andere[0].gesamt - beste.gesamt)} günstiger als '
               f'{escape(andere[0].anbieter)}</div>')
st.html(f"""
<div class="sieger">
  <div class="marke">Am günstigsten</div>
  <div class="preis">{euro(beste.gesamt)}</div>
  <div class="name">{escape(beste.anbieter)} · {escape(beste.option)}{" *" if beste.unsicher else ""}</div>
  {abstand}
</div>
""")

hoechster = max(e.gesamt for e in ergebnisse) or 1
zeilen = []
for i, e in enumerate(ergebnisse, 1):
    posten = "".join(f"<span>{escape(k)}</span><span>{euro(v)}</span>" for k, v in e.posten.items() if v)
    hinweise = "".join(f"<li>{escape(h)}</li>" for h in e.hinweise)
    zeilen.append(f"""
<details>
  <summary>
    <span class="nr">{i}</span>
    <span class="wer"><b>{escape(e.anbieter)}</b> <span>{escape(e.option)}{" *" if e.unsicher else ""}</span></span>
    <span class="betrag">{euro(e.gesamt)}</span>
    <span class="balken"><i style="width:{e.gesamt / hoechster * 100:.1f}%;background:{FARBEN.get(e.gruppe, '#6B675C')}"></i></span>
    <span class="meta">{escape(e.gruppe)} · {HUND.get(e.haustiere, escape(e.haustiere))} · Details</span>
  </summary>
  <div class="innen">
    <div class="posten">{posten}</div>
    {f"<ul>{hinweise}</ul>" if hinweise else ""}
  </div>
</details>""")
st.html(f'<div class="rang">{"".join(zeilen)}</div>')

fuss = " · ".join(f'<a href="{escape(t["quelle"])}">{escape(t["name"])}</a>: Stand {escape(str(t["stand"]))}'
                  for t in T["carsharing"])
stern = "* enthält nicht bestätigte Tarifwerte. " if any(e.unsicher for e in ergebnisse) else ""
st.html(f'<p class="fuss">{stern}Tarife: {fuss}. Einmalkosten wie Registrierung sind nicht enthalten.</p>')
