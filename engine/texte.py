"""Deutsche Zahlen- und Satzformate, ohne Streamlit."""
from __future__ import annotations

from .eigenauto import BreakEven
from .modelle import Profil


def euro(betrag: float, stellen: int = 2) -> str:
    return f"{betrag:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def zahl(wert: float, stellen: int = 1) -> str:
    return f"{wert:,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
