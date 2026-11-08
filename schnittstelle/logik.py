"""Schnittstellen-Logik für den CoS: JSON-Daten rein, (HTTP-Status, JSON-Daten) raus.

Keine HTTP-Details hier – die stehen in server.py. Geprüft wird alles, was von außen kommt:
unbekannte Felder, Typen und dieselben Grenzen wie in der App (engine/grenzen.py).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

import telemetrie
from engine import (NICHT_GEFAHREN, BahnAngebot, Eintrag, FreiesAngebot, Instanz, MietAngebot, Szenario,
                    break_even, reisende_text, vergleiche, zeitraeume, zeitraum, zeitraumkosten)
from engine.grenzen import EURO_MAX, KM_MAX, MEHR_KM_MAX, SPRIT_MAX, TEXT_MAX
from engine.schnappschuss import schnappschuss
from engine.suchlinks import suchlink
from engine.texte import break_even_satz
from speicher.fahrten import alle, anlegen, doppelt, holen, rechnung_nachtragen

ZEITFORMAT = "%Y-%m-%dT%H:%M"
REISE_FELDER = {"start", "ende", "km", "hund", "spritpreis", "km_paket", "selbstbehalt_reduzieren", "angebote"}
FAHRT_FELDER = REISE_FELDER | {"wahl", "eigenes_auto", "anlass"}
ANGEBOT_FELDER = {
    "miet": {"anbieter", "preis", "frei_km", "mehr_km", "extras"},
    "bahn": {"anbieter", "preis", "vor_ort"},
    "frei": {"anbieter", "preis", "beschreibung"},
}
ARTEN = ("monat", "quartal", "jahr", "gesamt")
JAHRE = (2000, 2100)   # schützt Kalenderrechnung und Tagesschleifen der Auswertung vor Unsinnsdaten


class Ungueltig(ValueError):
    """Eingabe abgelehnt – der Text geht als Fehlermeldung zurück."""


# ---------- Prüfen ----------

def _objekt(d, was: str = "Der Körper") -> dict:
    if not isinstance(d, dict):
        raise Ungueltig(f"{was} muss ein JSON-Objekt sein.")
    return d


def _nur(d: dict, erlaubt: set[str], wo: str = "") -> None:
    fremd = sorted(set(d) - erlaubt)
    if fremd:
        raise Ungueltig(f"Unbekanntes Feld{wo}: {', '.join(fremd)}.")


def _zahl(d: dict, feld: str, hoechstens: float, standard: float | None = None) -> float:
    if feld not in d:
        if standard is None:
            raise Ungueltig(f"Feld {feld} fehlt.")
        return standard
    wert = d[feld]
    if isinstance(wert, bool) or not isinstance(wert, (int, float)) or wert != wert:
        raise Ungueltig(f"Feld {feld} muss eine Zahl sein.")
    if not 0 <= wert <= hoechstens:
        raise Ungueltig(f"Feld {feld} muss zwischen 0 und {hoechstens:g} liegen.")
    return float(wert)


def _bool(d: dict, feld: str, standard: bool | None = None) -> bool:
    if feld not in d:
        if standard is None:
            raise Ungueltig(f"Feld {feld} fehlt.")
        return standard
    if not isinstance(d[feld], bool):
        raise Ungueltig(f"Feld {feld} muss true oder false sein.")
    return d[feld]


def _text(d: dict, feld: str, pflicht: bool = False) -> str:
    if feld not in d:
        if pflicht:
            raise Ungueltig(f"Feld {feld} fehlt.")
        return ""
    if not isinstance(d[feld], str):
        raise Ungueltig(f"Feld {feld} muss Text sein.")
    if len(d[feld]) > TEXT_MAX:
        raise Ungueltig(f"Feld {feld} darf höchstens {TEXT_MAX} Zeichen haben.")
    return d[feld].strip()


def _zeit(d: dict, feld: str) -> datetime:
    try:
        return datetime.strptime(str(d[feld]), ZEITFORMAT)
    except KeyError:
        raise Ungueltig(f"Feld {feld} fehlt.") from None
    except ValueError:
        raise Ungueltig(f"Feld {feld} bitte als JJJJ-MM-TTTHH:MM angeben.") from None


def reise_lesen(d, tarife: dict, instanz: Instanz, erlaubt: set[str] = REISE_FELDER):
    """→ (Szenario, Mietangebote, Bahn, Frei, normalisierte Reise)."""
    d = _objekt(d)
    _nur(d, erlaubt)
    start, ende = _zeit(d, "start"), _zeit(d, "ende")
    if not all(JAHRE[0] <= z.year <= JAHRE[1] for z in (start, ende)):
        raise Ungueltig(f"Jahr muss zwischen {JAHRE[0]} und {JAHRE[1]} liegen.")
    if ende <= start:
        raise Ungueltig("Die Rückgabe liegt vor der Abholung.")
    sz = Szenario(start=start, ende=ende, km=_zahl(d, "km", KM_MAX), spritpreis=_zahl(d, "spritpreis", SPRIT_MAX, 1.75),
                  hund=_bool(d, "hund", instanz.hund), km_paket_nutzen=_bool(d, "km_paket", True),
                  selbstbehalt_reduzieren=_bool(d, "selbstbehalt_reduzieren", False))
    mietwagen = {m["id"]: m for m in tarife["angebote"].get("mietwagen", [])}
    b = tarife["angebote"].get("bahn", {})
    roh = d.get("angebote", [])
    if not isinstance(roh, list):
        raise Ungueltig("Feld angebote muss eine Liste sein.")
    miet, bahn, frei, gesehen, normal = [], None, None, set(), []
    for a in roh:
        a = _objekt(a, "Ein Angebot")
        anbieter = a.get("anbieter")
        if not isinstance(anbieter, str) or (anbieter not in mietwagen and anbieter not in ("bahn", "frei")):
            erlaubt_ids = ", ".join([*mietwagen, "bahn", "frei"])
            raise Ungueltig(f"Unbekannter Anbieter „{anbieter}“ – erlaubt: {erlaubt_ids}.")
        if anbieter in gesehen:
            raise Ungueltig(f"Anbieter {anbieter} doppelt angegeben.")
        gesehen.add(anbieter)
        art = anbieter if anbieter in ("bahn", "frei") else "miet"
        _nur(a, ANGEBOT_FELDER[art], f" im Angebot {anbieter}")
        preis = _zahl(a, "preis", EURO_MAX)
        if art == "miet":
            m = mietwagen[anbieter]
            frei_km, mehr = _zahl(a, "frei_km", KM_MAX, 0), _zahl(a, "mehr_km", MEHR_KM_MAX, 0)
            extras = _zahl(a, "extras", EURO_MAX, 0)
            miet.append(MietAngebot(anbieter, m["name"], preis, frei_km, mehr, float(m.get("verbrauch_l_100km", 6.5)),
                                    extras, m.get("haustiere", "pruefen")))
            normal.append({"anbieter": anbieter, "preis": preis, "frei_km": frei_km, "mehr_km": mehr, "extras": extras})
        elif art == "bahn":
            vor_ort = _zahl(a, "vor_ort", EURO_MAX, 0)
            bahn = BahnAngebot(preis, vor_ort, b.get("haustiere", "ja"), reisende_text(instanz))
            normal.append({"anbieter": "bahn", "preis": preis, "vor_ort": vor_ort})
        else:
            text = _text(a, "beschreibung")
            frei = FreiesAngebot(text, preis)
            normal.append({"anbieter": "frei", "preis": preis, "beschreibung": text})
    reise = {"start": start.strftime(ZEITFORMAT), "ende": ende.strftime(ZEITFORMAT), "km": sz.km, "hund": sz.hund,
             "spritpreis": sz.spritpreis, "km_paket": sz.km_paket_nutzen,
             "selbstbehalt_reduzieren": sz.selbstbehalt_reduzieren, "angebote": normal}
    return sz, miet, bahn, frei, reise


# ---------- Antworten ----------

def _wahl(e) -> str:
    return f"{e.anbieter} · {e.option}"


def _rangzeile(e) -> dict:
    return {"wahl": _wahl(e), "anbieter": e.anbieter, "option": e.option, "gruppe": e.gruppe, "gesamt": e.gesamt,
            "posten": dict(e.posten), "hinweise": list(e.hinweise), "haustiere": e.haustiere, "unsicher": e.unsicher}


def _fahrt(e: Eintrag, jetzt: datetime) -> dict:
    return {"id": e.id, "start": e.start.strftime(ZEITFORMAT), "ende": e.ende.strftime(ZEITFORMAT),
            "anlass": e.anlass, "ergebnis": e.ergebnis, "gruppe": e.gruppe, "km_geplant": e.km_geplant,
            "km_tatsaechlich": e.km_tatsaechlich, "preis_geplant": e.preis_geplant,
            "preis_tatsaechlich": e.preis_tatsaechlich, "eigenauto_gefahren": e.eigenauto_gefahren,
            "rechnung_offen": e.rechnung_offen(jetzt)}


def _suchlinks(tarife: dict, start: datetime, ende: datetime) -> dict[str, str]:
    links = {m["id"]: suchlink(m, start, ende) for m in tarife["angebote"].get("mietwagen", [])}
    b = tarife["angebote"].get("bahn")
    if b:
        links["bahn"] = suchlink({"link": "https://www.bahn.de", **b}, start, ende)
    return links


def _fehler(e: Exception) -> tuple[int, dict]:
    return 400, {"fehler": str(e)}


def vergleich(koerper, tarife: dict, instanz: Instanz) -> tuple[int, dict]:
    try:
        sz, miet, bahn, frei, reise = reise_lesen(koerper, tarife, instanz)
    except Ungueltig as e:
        return _fehler(e)
    erg = vergleiche(tarife, sz, miet, bahn, frei)
    return 200, {"reise": reise, "rangliste": [_rangzeile(e) for e in erg],
                 "suchlinks": _suchlinks(tarife, sz.start, sz.ende)}


def fahrt_anlegen(koerper, tarife: dict, instanz: Instanz, con: sqlite3.Connection,
                  jetzt: datetime | None = None) -> tuple[int, dict]:
    try:
        sz, miet, bahn, frei, _ = reise_lesen(koerper, tarife, instanz, FAHRT_FELDER)
        wahl = _text(koerper, "wahl", pflicht=True)
        eigen = _bool(koerper, "eigenes_auto")
        anlass = _text(koerper, "anlass", pflicht=True)
    except Ungueltig as e:
        return _fehler(e)
    erg = vergleiche(tarife, sz, miet, bahn, frei)
    gewaehlt = next((e for e in erg if _wahl(e) == wahl), None)
    if gewaehlt is None and wahl != NICHT_GEFAHREN:
        vorhanden = ", ".join(_wahl(e) for e in erg) or "keine"
        return 400, {"fehler": f"Wahl „{wahl}“ steht nicht in der Rangliste (vorhanden: {vorhanden}, {NICHT_GEFAHREN})."}
    e = Eintrag(start=sz.start, ende=sz.ende, anlass=anlass, ergebnis=wahl,
                gruppe=gewaehlt.gruppe if gewaehlt else "keine", km_geplant=sz.km,
                preis_geplant=gewaehlt.gesamt if gewaehlt else 0.0, eigenauto_gefahren=eigen,
                vergleich=schnappschuss(sz, erg, tarife))
    schon = doppelt(con, e)
    if schon is not None:
        return 409, {"fehler": f"Diese Fahrt ist schon gespeichert (#{schon}).", "id": schon}
    e.id = anlegen(con, e)
    telemetrie.senden("entscheidung", telemetrie.entscheidung_daten(e))
    return 201, {"fahrt": _fahrt(holen(con, e.id), jetzt or datetime.now())}


def fahrten(query: dict[str, str], con: sqlite3.Connection, jetzt: datetime) -> tuple[int, dict]:
    if set(query) - {"offen", "anzahl"}:
        return 400, {"fehler": f"Unbekannter Parameter: {', '.join(sorted(set(query) - {'offen', 'anzahl'}))}."}
    offen = query.get("offen", "0")
    if offen not in ("0", "1"):
        return 400, {"fehler": "Parameter offen muss 0 oder 1 sein."}
    try:
        anzahl = int(query.get("anzahl", "20"))
    except ValueError:
        anzahl = 0
    if not 1 <= anzahl <= 100:
        return 400, {"fehler": "Parameter anzahl muss zwischen 1 und 100 liegen."}
    liste = [e for e in alle(con) if offen == "0" or e.rechnung_offen(jetzt)]
    return 200, {"fahrten": [_fahrt(e, jetzt) for e in liste[:anzahl]]}


def rechnung(id_text: str, koerper, con: sqlite3.Connection, jetzt: datetime | None = None) -> tuple[int, dict]:
    e = holen(con, int(id_text)) if id_text.isdigit() else None
    if e is None:
        return 404, {"fehler": f"Fahrt #{id_text} gibt es nicht."}
    try:
        koerper = _objekt(koerper)
        _nur(koerper, {"preis_tatsaechlich", "km_tatsaechlich"})
        preis = _zahl(koerper, "preis_tatsaechlich", EURO_MAX)
        km = _zahl(koerper, "km_tatsaechlich", KM_MAX) if "km_tatsaechlich" in koerper else None
    except Ungueltig as x:
        return _fehler(x)
    if not e.gefahren:
        return 400, {"fehler": f"Fahrt #{e.id} ist als „{NICHT_GEFAHREN}“ gespeichert – keine Rechnung."}
    rechnung_nachtragen(con, e.id, preis, km)
    return 200, {"fahrt": _fahrt(holen(con, e.id), jetzt or datetime.now())}


def auswertung(query: dict[str, str], tarife: dict, con: sqlite3.Connection, heute: date) -> tuple[int, dict]:
    art = query.get("zeitraum", "quartal")
    if art not in ARTEN:
        return 400, {"fehler": f"Parameter zeitraum muss einer von {', '.join(ARTEN)} sein."}
    try:
        bezug = date.fromisoformat(query["datum"]) if query.get("datum") else heute
    except ValueError:
        return 400, {"fehler": "Parameter datum bitte als JJJJ-MM-TT angeben."}
    eintraege = alle(con)
    profile = tarife["eigenauto"]
    hinweise = list(tarife["hinweise"])
    offen = sum(e.rechnung_offen(datetime.now()) for e in eintraege)
    if not eintraege or not profile:
        hinweise.insert(0, "Noch keine Fahrten gespeichert." if not eintraege
                        else "Es sind keine Profile für ein eigenes Auto geladen.")
        return 200, {"zeitraum": None, "profile": [], "offene_rechnungen": offen, "hinweise": hinweise}
    zr = (zeitraeume("gesamt", eintraege, heute)[0] if art == "gesamt" else zeitraum(art, bezug, heute))
    zeilen = []
    for p in profile:
        k = zeitraumkosten(eintraege, p, zr)
        zeilen.append({"id": p.id, "name": p.name, "ist": k.ist, "mit_profil": k.mit_profil, "differenz": k.differenz,
                       "break_even": break_even_satz(p, break_even(eintraege, p, heute))})
    zeilen.sort(key=lambda z: z["differenz"])
    return 200, {"zeitraum": {"art": zr.art, "label": zr.label, "von": zr.von.isoformat(), "bis": zr.bis.isoformat()},
                 "profile": zeilen, "offene_rechnungen": offen, "hinweise": hinweise}
