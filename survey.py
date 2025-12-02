# ============================================
# survey.py – Abschlussfragebogen für Verhandlungs-Bot
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

    # ---------------------------
    # 2. Geschlecht
    # ---------------------------
    gender = st.selectbox(
        "2. Mit welchem Geschlecht identifizieren Sie sich?",
        ["männlich", "weiblich", "divers", "keine Antwort"]
    )

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

    # ---------------------------
    # 5. Zufriedenheit Ergebnis
    # ---------------------------
    satisfaction_outcome = st.slider(
        "5. Wie zufrieden sind Sie mit dem Ergebnis der Verhandlung?",
        1, 10, 5
    )

    # ---------------------------
    # 6. Zufriedenheit Verlauf
    # ---------------------------
    satisfaction_process = st.slider(
        "6. Wie zufriedenstellend fanden Sie den Verhandlungsverlauf?",
        1, 10, 5
    )

    # ---------------------------
    # 7. Gefühl, besseres Ergebnis möglich?
    # ---------------------------
    better_result = st.slider(
        "7. Haben Sie das Gefühl, Sie hätten ein besseres Verhandlungsergebnis erzielen können (preislich)?",
        1, 10, 5
    )

    # ---------------------------
    # 8. Abweichung vom normalen Verhalten
    # ---------------------------
    deviation = st.selectbox(
        "8. Inwiefern sind Sie während der Verhandlung von Ihrem normalen Verhandlungsverhalten abgewichen?",
        [
            "stark dominant",
            "leicht dominant",
            "keine Abweichung",
            "leicht nachgiebig",
            "stark nachgiebig"
        ]
    )

    # ---------------------------
    # 9. Verhandlungsbereitschaft im Alltag
    # ---------------------------
    willingness = st.slider(
        "9. Wie hoch ist Ihre Bereitschaft zu verhandeln im Alltag?",
        1, 10, 5,
        help="1 = Ich sehe einen festen Preis als gegeben, 10 = Ich verhandle über jeden Preis"
    )

    # ---------------------------
    # 10. Wiederverhandlung?
    # ---------------------------
    again = st.selectbox(
        "10. Würden Sie nochmal mit dem Bot verhandeln wollen?",
        ["Ja", "Nein"]
    )

    st.markdown("---")

    # ---------------------------
    # Absenden
    # ---------------------------
    submit = st.button("Fragebogen absenden")

    if submit:
        st.success("Vielen Dank für Ihre Teilnahme! Die Daten wurden gespeichert.")

        # Rückgabe an das Hauptsystem zur Speicherung
        return {
            "age": age,
            "gender": gender,
            "education": education,
            "field": field,
            "field_other": field_other,
            "satisfaction_outcome": satisfaction_outcome,
            "satisfaction_process": satisfaction_process,
            "better_result": better_result,
            "deviation": deviation,
            "willingness": willingness,
            "again": again
        }

    return None
