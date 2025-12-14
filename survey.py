# ============================================
# survey.py – Abschlussfragebogen (1–6 Skalen, ohne Vorauswahl)
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
    # 2. Geschlecht – keine Vorauswahl
    # ---------------------------
    st.write("2. Mit welchem Geschlecht identifizieren Sie sich?")

    gender = st.radio(
        "",
        ["männlich", "weiblich", "divers"],
        index=None,
        horizontal=True,
        label_visibility="collapsed",
        key="gender"
    )

    st.markdown("---")

    # ---------------------------
    # 3. Bildungsabschluss – keine Vorauswahl
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
            "Diplom",
            "Master",
            "Staatsexamen",
            "Promotion",
            "Habilitation",
            "Sonstiger Abschluss"
        ],
        index=None
    )

    st.markdown("---")

    # ---------------------------
    # 4. Fachbereich (optional)
    # ---------------------------
    field = None
    field_other = None

    if education in [
        "Bachelor", "Master", "Diplom",
        "Staatsexamen", "Promotion",
        "Habilitation", "Sonstiger Abschluss"
    ]:
        field = st.selectbox(
            "4. In welchem Fachbereich liegt Ihr Studium / Abschluss?",
            [
                "Architektur, Bauingenieurwesen und Geomatik",
                "Informatik und Ingenieurwissenschaften",
                "Wirtschaft und Recht",
                "Soziale Arbeit und Gesundheit",
                "Andere"
            ],
            index=None
        )

        if field == "Andere":
            field_other = st.text_input("Bitte geben Sie an, welcher Fachbereich:")

    st.markdown("---")

    # -------------------------------------------------------
    # Hilfsfunktion: Skala 1–6 OHNE Vorauswahl
    # -------------------------------------------------------
    def labeled_select_scale(question, left_label, right_label, key):
        st.write(question)

        value = st.select_slider(
            label="",
            options=[1, 2, 3, 4, 5, 6],
            value=None,                     # keine Vorauswahl
            key=key,
            label_visibility="collapsed"
        )

        col_l, col_r = st.columns(2)
        with col_l:
            st.caption(f"1 = {left_label}")
        with col_r:
            st.caption(f"6 = {right_label}")

        st.markdown("")
        return value

    # ---------------------------
    # 5. Zufriedenheit Ergebnis (1–6)
    # ---------------------------
    satisfaction_outcome = labeled_select_scale(
        "5. Wie zufrieden sind Sie mit dem Ergebnis der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        key="s_outcome"
    )
    st.markdown("---")

    # ---------------------------
    # 6. Zufriedenheit Verlauf (1–6)
    # ---------------------------
    satisfaction_process = labeled_select_scale(
        "6. Wie zufriedenstellend fanden Sie den Verlauf der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        key="s_process"
    )
    st.markdown("---")

    # ---------------------------
    # 7. Preisliches Ergebnis (1–6)
    # ---------------------------
    better_result = labeled_select_scale(
        "7. Hätten Sie ein besseres preisliches Ergebnis erzielen können?",
        "keine preisliche Verbesserung",
        "viel bessere preisliche Verbesserung",
        key="s_better"
    )
    st.markdown("---")

    # ---------------------------
    # 8. Abweichung Verhandlungsstil (1–6)
    # ---------------------------
    st.write("8. Wie stark sind Sie von Ihrem normalen Verhandlungsverhalten abgewichen?")

    deviation = st.select_slider(
        label="",
        options=[1, 2, 3, 4, 5, 6],
        value=None,
        label_visibility="collapsed",
        key="s_deviation"
    )

    labels = {
        1: "sehr nachgiebig",
        2: "nachgiebig",
        3: "leicht nachgiebig",
        4: "leicht dominant",
        5: "dominant",
        6: "sehr dominant"
    }

    st.caption("   ".join([f"{i} = {labels[i]}" for i in range(1, 7)]))
    st.markdown("---")

    # ---------------------------
    # 9. Verhandlungsbereitschaft im Alltag (1–6)
    # ---------------------------
    willingness = labeled_select_scale(
        "9. Wie hoch ist Ihre Bereitschaft zu verhandeln im Alltag?",
        "ich verhandle nie",
        "ich verhandle fast immer",
        key="s_willing"
    )
    st.markdown("---")

    # ---------------------------
    # 10. Wiederverhandlung – keine Vorauswahl
    # ---------------------------
    st.write("10. Würden Sie erneut mit dem Bot verhandeln wollen?")

    again = st.radio(
        "",
        ["Ja", "Nein"],
        index=None,
        horizontal=True,
        label_visibility="collapsed",
        key="again"
    )

    st.markdown("---")

    # ---------------------------
    # Absenden
    # ---------------------------
    submit = st.button("Fragebogen absenden")

    if submit:
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
