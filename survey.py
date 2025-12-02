# ============================================
# survey.py – Abschlussfragebogen (mit Punkteskalen & 4 Geschlechtsoptionen)
# ============================================

import streamlit as st

def show_survey():

    # ================================
    # Optische Punkteskala (●/○) unter dem Slider
    # ================================
    def point_scale(question, left_label, right_label, key, steps=10, default=None):
        """
        Zeigt:
        - Frage
        - Slider 1..steps
        - Darunter eine Zeile mit Punkten (● für ausgewählten Wert, ○ für die anderen)
        - Links/Rechts-Beschriftung (1 = left_label, steps = right_label)
        """
        st.write(question)

        if default is None:
            default = (steps + 1) // 2  # Mittelwert als Start

        value = st.slider(
            label="",
            min_value=1,
            max_value=steps,
            value=default,
            step=1,
            key=key,
            label_visibility="collapsed"
        )

        # Punktezeile aufbauen
        dots = []
        for i in range(1, steps + 1):
            if i == value:
                dots.append("●")
            else:
                dots.append("○")

        # Punkte optisch zentriert & etwas größer darstellen
        st.markdown(
            f"<p style='font-size: 24px; text-align: center; margin: 0;'>{' '.join(dots)}</p>",
            unsafe_allow_html=True
        )

        # Beschriftungen links und rechts
        col_l, col_r = st.columns(2)
        with col_l:
            st.caption(f"1 = {left_label}")
        with col_r:
            st.caption(f"{steps} = {right_label}")

        st.markdown("")  # kleiner Abstand unten
        return value

    # ================================
    # Fragebogen Kopf
    # ================================
    st.markdown("## 📋 Abschlussfragebogen zur Verhandlung")
    st.info("Bitte füllen Sie den Fragebogen aus. Ihre Antworten bleiben anonym.")
    st.markdown("---")

    # 1. Alter
    age = st.text_input("1. Wie alt sind Sie?")
    st.markdown("---")

    # 2. Geschlecht – alle vier Optionen direkt sichtbar
    st.write("2. Mit welchem Geschlecht identifizieren Sie sich?")

    # Eine Radio-Gruppe mit allen 4 Optionen, direkt sichtbar
    # (Streamlit sorgt dafür, dass das auf kleineren Screens ggf. umbricht)
    gender = st.radio(
        "",
        ["männlich", "weiblich", "divers", "keine Angabe"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("---")

    # 3. Bildungsabschluss
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

    # 4. Fachbereich (optional)
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

    # 5. Zufriedenheit mit dem Ergebnis (1–10, sehr unzufrieden – sehr zufrieden)
    satisfaction_outcome = point_scale(
        "5. Wie zufrieden sind Sie mit dem Ergebnis der Verhandlung?",
        left_label="sehr unzufrieden",
        right_label="sehr zufrieden",
        key="s_outcome",
        steps=10
    )

    st.markdown("---")

    # 6. Zufriedenheit mit dem Verlauf (1–10)
    satisfaction_process = point_scale(
        "6. Wie zufriedenstellend fanden Sie den Verlauf der Verhandlung?",
        left_label="sehr unzufrieden",
        right_label="sehr zufrieden",
        key="s_process",
        steps=10
    )

    st.markdown("---")

    # 7. Preisliches Ergebnis (1–10, keine Verbesserung – viel bessere Verbesserung)
    better_result = point_scale(
        "7. Hätten Sie ein besseres preisliches Ergebnis erzielen können?",
        left_label="keine preisliche Verbesserung",
        right_label="viel bessere preisliche Verbesserung",
        key="s_better",
        steps=10
    )

    st.markdown("---")

    # 8. Dominanz / Nachgiebigkeit (1–5, alle Stufen beschriftet)
    st.write("8. Wie stark sind Sie von Ihrem normalen Verhandlungsverhalten abgewichen?")

    deviation = st.slider(
        label="",
        min_value=1,
        max_value=5,
        value=3,
        step=1,
        label_visibility="collapsed",
        key="s_deviation"
    )

    # Alle Stufen textlich darstellen
    labels = {
        1: "stark nachgiebig",
        2: "leicht nachgiebig",
        3: "keine Abweichung",
        4: "leicht dominant",
        5: "stark dominant"
    }

    st.markdown(
        "<p style='text-align: center; margin: 0;'>"
        + " &nbsp;&nbsp; ".join([f"{i} = {txt}" for i, txt in labels.items()])
        + "</p>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    # 9. Verhandlungsbereitschaft im Alltag (1–10)
    willingness = point_scale(
        "9. Wie hoch ist Ihre Bereitschaft zu verhandeln im Alltag?",
        left_label="ich verhandle nie",
        right_label="ich verhandle fast immer",
        key="s_willing",
        steps=10
    )

    st.markdown("---")

    # 10. Würden Sie erneut mit dem Bot verhandeln? (Ja/Nein anklickbar)
    st.write("10. Würden Sie erneut mit dem Bot verhandeln wollen?")
    again = st.radio(
        "",
        ["Ja", "Nein"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Absenden
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
