"""Wie fahren wir? – Mobilitäts-Vergleich für Familie mit Hund (Kassel)."""
import streamlit as st

from seiten.gemeinsam import eingaben_halten, gestaltung

st.set_page_config(page_title="Wie fahren wir?", page_icon=":material/directions_car:", layout="centered")
gestaltung()
eingaben_halten()

st.navigation([
    st.Page("seiten/vergleich.py", title="Vergleich", default=True),
    st.Page("seiten/fahrten.py", title="Fahrten", url_path="fahrten"),
    st.Page("seiten/auswertung.py", title="Auswertung", url_path="auswertung"),
], position="top").run()
