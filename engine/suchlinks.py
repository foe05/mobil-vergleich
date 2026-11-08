"""Suchseiten der Anbieter mit Ort und Reisezeit vorbelegt."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, urlencode


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


def aus_link(q) -> dict | None:
    """Reise aus den Link-Parametern der App (start, ende, km, hund, anlass) für den Session State.
    None, wenn etwas fehlt oder nicht passt – dann gilt der normale Start mit Vorlage."""
    from .grenzen import KM_MAX, TEXT_MAX
    try:
        start = datetime.strptime(q["start"], "%Y-%m-%dT%H:%M")
        ende = datetime.strptime(q["ende"], "%Y-%m-%dT%H:%M")
        km = int(q["km"])
    except (KeyError, TypeError, ValueError):
        return None
    if ende <= start or not 0 <= km <= KM_MAX:
        return None
    werte = {"start_d": start.date(), "start_t": start.time(), "ende_d": ende.date(), "ende_t": ende.time(), "km": km}
    if "hund" in q:
        if q["hund"] not in ("0", "1"):
            return None
        werte["hund"] = q["hund"] == "1"
    if q.get("anlass"):
        werte["anlass"] = str(q["anlass"]).strip()[:TEXT_MAX]
    return werte
