"""Preislogik. Reine Funktionen, keine Streamlit-Abhängigkeit -> gut testbar."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from .modelle import BahnAngebot, Ergebnis, FreiesAngebot, MietAngebot, Szenario


# ---------- Zeit ----------

def abgerechnete_minuten(minuten: int, takt: int, erste_stunde_voll: bool) -> int:
    if minuten <= 0:
        return 0
    if erste_stunde_voll and minuten <= 60:
        return 60
    return math.ceil(minuten / takt) * takt


def zeitkosten(stunden: float, stundenpreis: float, tagespreis: float | None,
               wochenpreis: float | None) -> float:
    """Günstigste Kombination aus Stunden-, Tages- und Wochenpreis.
    Tag = 24 h, Woche = 7 × 24 h ab Buchungsbeginn."""

    def tage(h: float) -> float:
        if not tagespreis:
            return h * stundenpreis
        d, rest = divmod(h, 24)
        return d * tagespreis + min(tagespreis, rest * stundenpreis)

    if not wochenpreis:
        return tage(stunden)
    w, rest = divmod(stunden, 168)
    return w * wochenpreis + min(wochenpreis, tage(rest))


# ---------- Pauschalen (z. B. Flinkster-Wochenende) ----------

def _passt_in_wochenende(start: datetime, ende: datetime) -> bool:
    """Fr 07:00 bis Mo 07:00 desselben Wochenendes."""
    tage_seit_freitag = (start.weekday() - 4) % 7
    freitag = (start - timedelta(days=tage_seit_freitag)).replace(hour=7, minute=0, second=0, microsecond=0)
    if freitag > start:
        freitag -= timedelta(days=7)
    return start >= freitag and ende <= freitag + timedelta(days=3)


def _passt_in_sa_so_tag(start: datetime, ende: datetime) -> bool:
    """Buchung liegt komplett an einem Samstag oder Sonntag (0:00–23:59)."""
    if start.weekday() not in (5, 6):
        return False
    mitternacht = datetime.combine(start.date() + timedelta(days=1), datetime.min.time())
    return ende.date() == start.date() or ende == mitternacht


PAUSCHAL_PRUEFUNG = {
    "wochenende": _passt_in_wochenende,
    "sa_so_tag": _passt_in_sa_so_tag,
}


# ---------- Carsharing ----------

def berechne_carsharing(tarif: dict, klasse: dict, sz: Szenario) -> Ergebnis:
    minuten = abgerechnete_minuten(sz.minuten, tarif.get("takt_minuten", 15),
                                   tarif.get("erste_stunde_voll", False))
    h = minuten / 60

    # km-Preis: Paket (falls vorhanden und gewünscht) oder regulär
    paket = tarif.get("km_paket")
    km_preis = paket["km_preis"] if (paket and sz.km_paket_nutzen) else klasse["km_preis"]

    def variante(zeit: float, frei_km: float, label: str | None):
        km_kosten = max(0.0, sz.km - frei_km) * km_preis
        return zeit, km_kosten, label

    varianten = [variante(zeitkosten(h, klasse["stundenpreis"], klasse.get("tagespreis"),
                                     klasse.get("wochenpreis")), 0, None)]
    for p in tarif.get("pauschalen", []) or []:
        pruef = PAUSCHAL_PRUEFUNG.get(p["art"])
        if pruef and pruef(sz.start, sz.ende):
            regulaer = zeitkosten(h, klasse["stundenpreis"], klasse.get("tagespreis"), klasse.get("wochenpreis"))
            # Konservativ: Freikilometer nur, wenn der Pauschal-Deckel wirklich greift
            if p["preis"] < regulaer:
                varianten.append(variante(p["preis"], p.get("frei_km", 0), p["name"]))

    zeit, km_kosten, pauschale = min(varianten, key=lambda v: v[0] + v[1])

    posten = {"Zeit": zeit, "Kilometer": km_kosten, "Start-/Buchungsgebühr": tarif.get("startpreis", 0.0)}
    hinweise = list(tarif.get("hinweise", []))
    if pauschale:
        hinweise.insert(0, f"Pauschale angewendet: {pauschale}")
    if sz.selbstbehalt_reduzieren and tarif.get("selbstbehalt_reduktion"):
        posten["Selbstbehalt-Reduktion"] = tarif["selbstbehalt_reduktion"]
    if paket and sz.km_paket_nutzen:
        hinweise.append(f"Mit {paket['km']}-km-Paket ({paket['preis']:.0f} €) gerechnet – "
                        "Restkilometer verfallen nicht.")
    if not tarif.get("sprit_inklusive", False):
        posten["Sprit"] = sz.km * klasse.get("verbrauch_l_100km", 6.5) / 100 * sz.spritpreis

    unverif = klasse.get("unverifiziert") or []
    if unverif:
        hinweise.append("Nicht verifiziert: " + ", ".join(unverif))

    return Ergebnis(
        anbieter=tarif["name"], option=klasse["name"], gruppe="Carsharing",
        gesamt=round(sum(posten.values()), 2), posten={k: round(v, 2) for k, v in posten.items()},
        hinweise=hinweise, haustiere=tarif.get("haustiere", "pruefen"), unsicher=bool(unverif),
    )


# ---------- Mietwagen (Angebotspreis + Sprit) ----------

def berechne_mietwagen(a: MietAngebot, sz: Szenario) -> Ergebnis:
    mehr_km = max(0.0, sz.km - a.frei_km) if a.frei_km else 0.0
    posten = {
        "Miete laut Angebot": a.preis_gesamt,
        "Mehrkilometer": mehr_km * a.mehr_km_preis,
        "Sprit": sz.km * a.verbrauch_l_100km / 100 * sz.spritpreis,
        "Extras": a.extras,
    }
    hinweise = [f"Preis {a.quelle} eingetragen", f"Sprit geschätzt: {a.verbrauch_l_100km} l/100 km"]
    return Ergebnis(
        anbieter=a.name, option="Angebot", gruppe="Mietwagen",
        gesamt=round(sum(posten.values()), 2), posten={k: round(v, 2) for k, v in posten.items()},
        hinweise=hinweise, haustiere=a.haustiere,
    )


def berechne_bahn(b: BahnAngebot) -> Ergebnis:
    posten = {"Tickets": b.preis_gesamt, "Mobilität vor Ort": b.vor_ort}
    return Ergebnis(
        anbieter="Bahn", option="Familie + Hund", gruppe="Bahn",
        gesamt=round(sum(posten.values()), 2), posten=posten,
        hinweise=["Preis manuell eingetragen"], haustiere=b.haustiere,
    )


def berechne_frei(a: FreiesAngebot) -> Ergebnis:
    return Ergebnis(
        anbieter=a.beschreibung.strip() or "Freies Angebot", option="freies Angebot", gruppe="Sonstiges",
        gesamt=round(a.preis_gesamt, 2), posten={"Gesamtpreis": a.preis_gesamt},
        hinweise=["Preis manuell eingetragen"], haustiere="pruefen",
    )


# ---------- Alles zusammen ----------

def vergleiche(tarife: dict, sz: Szenario, miet: list[MietAngebot],
               bahn: BahnAngebot | None, frei: FreiesAngebot | None = None) -> list[Ergebnis]:
    ergebnisse: list[Ergebnis] = []
    for t in tarife["carsharing"]:
        for k in t["klassen"]:
            if k.get("familientauglich", True):
                ergebnisse.append(berechne_carsharing(t, k, sz))
    ergebnisse += [berechne_mietwagen(a, sz) for a in miet if a.preis_gesamt > 0]
    if bahn and bahn.preis_gesamt > 0:
        ergebnisse.append(berechne_bahn(bahn))
    if frei and frei.preis_gesamt > 0:
        ergebnisse.append(berechne_frei(frei))
    if sz.hund:
        ergebnisse = [e for e in ergebnisse if e.haustiere != "nein"]
    return sorted(ergebnisse, key=lambda e: e.gesamt)
