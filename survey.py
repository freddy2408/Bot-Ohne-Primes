# ============================================
# survey.py – Abschlussfragebogen für Verhandlungs-Bot (überarbeitet)
# ============================================

import streamlit as st

def show_survey():
    st.markdown("## 📋 Abschlussfragebogen zur Verhandlung")
    st.info("Bitte füllen Sie den Fragebogen aus. Ihre Antworten bleiben anonym.")
    st.markdown("---")

    # ---------------------------
    # 1. Alter
    # ---------------------------
    age = st.text_input("1. Wie alt sind Sie?")

    st.markdown("---")

    # ---------------------------
    # 2. Geschlecht (Layout angepasst)
    # ---------------------------
    st.write("2. Mit welchem Geschlecht identifizieren Sie sich?")

    col1, col2 = st.columns(2)
    with col1:
        gender_top = st.radio(" ", ["männlich"], label_visibility="collapsed")
    with col2:
        gender_top2 = st.radio("  ", ["weiblich"], label_visibility="collapsed")

    gender_bottom = st.radio("   ", ["divers", "keine Angabe"], label_visibility="collapsed")

    # Auswahl zusammenführen
    if gender_top == "männlich":
        gender = "männlich"
    elif gender_top2 == "weiblich":
        gender = "weiblich"
    else:
        gender = gender_bottom

    st.markdown("---")

    # ---------------------------
    # 3. Bildungsabschluss
    # ---------------------------
    education = st.selectbox(
        "3. Welcher ist Ihr höchster Bildungsabschluss?",
        [
            "Kein Abschluss",
            "Hauptschulabschluss",
            "Realschulabschluss / Mittlere Reife",
            "Fachhochschulreife",
            "Allgemeine Hochschulreife (Abitur)",
            "Berufsausbildung",
            "Bachelor",
            "Master",
            "Diplom",
            "Staatsexamen",
            "Promotion",
            "Habilitation",
            "Sonstiger Abschluss"
        ]
    )

    st.markdown("---")

    # ---------------------------
    # 4. Fachbereich (optional)
    # ---------------------------
    field = None
    field_other = None

    if education in ["Bachelor", "Master", "Diplom", "Staatsexamen", "Promotion", "Habilitation", "Sonstiger Abschluss"]:
        field = st.selectbox(
            "4. Wenn Sie studieren oder einen höheren Bildungsabschluss haben: In welchem Fachbereich liegt das?",
            [
                "Architektur, Bauingenieurwesen und Geomatik",
                "Informatik und Ingenieurwissenschaften",
                "Wirtschaft und Recht",
                "Soziale Arbeit und Gesundheit",
                "Andere"
            ]
        )

        if field == "Andere":
            field_other = st.text_input("Bitte geben Sie an, welcher Fachbereich:")

    st.markdown("---")

    # ---------------------------
    # Hilfsfunktion Skala 1–10 mit Labels links/rechts
    # ---------------------------
    def scale(question, left, right, key):
        st.write(question)
        val = st.slider("", 1, 10, 5, key=key)

        col_l, col_r = st.columns(2)
        with col_l:
            st.caption(f"1 = {left}")
        with col_r:
            st.caption(f"10 = {right}")

        return val

    # ---------------------------
    # 5. Zufriedenheit Ergebnis
    # ---------------------------
    satisfaction_outcome = scale(
        "5. Wie zufrieden sind Sie mit dem Ergebnis der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        "s1"
    )

    st.markdown("---")

    # ---------------------------
    # 6. Zufriedenheit Verlauf
    # ---------------------------
    satisfaction_process = scale(
        "6. Wie zufriedenstellend fanden Sie den Verhandlungsverlauf?",
        "sehr unzufrieden",
        "sehr zufrieden",
        "s2"
    )

    st.markdown("---")

    # ---------------------------
    # 7. Gefühl, besseres Ergebnis möglich
