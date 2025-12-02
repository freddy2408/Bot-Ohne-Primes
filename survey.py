# ============================================
# survey.py – Abschlussfragebogen (voll überarbeitet)
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
    # 2. Geschlecht – oben m/w, unten d/keine Angabe
    # ---------------------------
    st.write("2. Mit welchem Geschlecht identifizieren Sie sich?")

    col1, col2 = st.columns(2)
    with col1:
        g1 = st.radio(" ", ["männlich"], label_visibility="collapsed")
    with col2:
        g2 = st.radio("  ", ["weiblich"], label_visibility="collapsed")

    g3 = st.radio("   ", ["divers", "keine Angabe"], label_visibility="collapsed")

    # Logik: welcher Radio wurde gedrückt?
    if g1 == "männlich":
        gender = "männlich"
    elif g2 == "weiblich":
        gender = "weiblich"
    else:
        gender = g3

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
            "4. In welchem Fachbereich liegt Ihr Studium / Abschluss?",
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

    # -------------------------------------------------------
    # Hilfsfunktion: Skala 1–10 mit linker und rechter Beschriftung
    # -------------------------------------------------------
    def labeled_scale(question, left_label, right_label, key):
        st.write(question)
        value = st.slider("", 1, 10, 5, key=key)
        col_l, col_r = st.columns(2)
        with col_l:
            st.caption(f"1 = {left_label}")
        with col_r:
            st.caption(f"10 = {right_label}")
        return value

    # ---------------------------
    # 5. Zufriedenheit Ergebnis
    # ---------------------------
    satisfaction_outcome = labeled_scale(
        "5. Wie zufrieden sind Sie mit dem Ergebnis der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        "s_outcome"
    )

    st.markdown("---")

    # ---------------------------
    # 6. Zufriedenheit Verlauf
    # ---------------------------
    satisfaction_process = labeled_scale(
        "6. Wie zufriedenstellend fanden Sie den Verlauf der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        "s_process"
    )

    st.markdown("---")

    # ---------------------------
    # 7. Gefühl, besseres Ergebnis möglich?
    # ---------------------------
    better_result = labeled_scale(
        "7. Hätten Sie ein besseres preisliches Ergebnis erzielen können?",
        "kein besseres Ergebnis",
        "viel besseres Ergebnis",
        "s_better"
    )

    st.markdown("---")

    # ---------------------------
    # 8. Abweichung vom normalen Verhalten – SKALA 1–5
    # ---------------------------
    st.write("8. Wie stark sind Sie von Ihrem normalen Verhandlungsverhalten abgewichen?")

    deviation = st.slider("", 1, 5, 3)

    labels = {
        1: "stark nachgiebig",
        2: "leicht nachgiebig",
        3: "keine Abweichung",
        4: "leicht dominant",
        5: "stark dominant"
    }

    # Label direkt unter Skala anzeigen
    st.caption("   ".join([f"{i} = {labels[i]}" for i in range(1, 6)]))

    st.markdown("---")

    # ---------------------------
    # 9. Verhandlungsbereitschaft im Alltag (1–10)
    # ---------------------------
    willingness = labeled_scale(
        "9. Wie hoch ist Ihre Bereitschaft zu verhandeln im Alltag?",
        "ich verhandle nie",
        "ich verhandle fast immer",
        "s_willing"
    )

    st.markdown("---")

    # ---------------------------
    # 10. Wiederverhandlung? (Ja / Nein nebeneinander)
    # ---------------------------
    st.write("10. Würden Sie erneut mit dem Bot verhandeln wollen?")

    col1, col2 = st.columns(2)
    with col1:
        ans_yes = st.radio(" ", ["Ja"], label_visibility="collapsed")
    with col2:
        ans_no = st.radio("  ", ["Nein"], label_visibility="collapsed")

    again = "Ja" if ans_yes == "Ja" else "Nein"

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
