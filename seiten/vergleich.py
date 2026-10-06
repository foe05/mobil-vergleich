"""Seite Vergleich: Reise eingeben, Optionen vergleichen."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from html import escape
from urllib.parse import quote, urlencode

import streamlit as st

from engine import BahnAngebot, MietAngebot, Szenario, vergleiche
from seiten.gemeinsam import GRUPPENFARBEN, euro, modus, tarife, zahl, zeitpunkt

HUND = {"ja": "Hund erlaubt", "nein": "Hund nicht erlaubt", "pruefen": "Hunderegel prüfen"}
FARBEN = GRUPPENFARBEN[modus()]


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
