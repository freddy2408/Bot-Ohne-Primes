# ============================================
# survey.py – Abschlussfragebogen (mit Punkteskalen + responsiver Geschlechtsauswahl)
# ============================================

import streamlit as st

def show_survey():

    # ================================
    # Custom CSS
    # ================================
    st.markdown("""
    <style>

    /* Responsive Grid für Geschlecht */
    .gender-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 4px;
        margin-bottom: 5px;
    }

    /* Punkteskala Darstellung */
    .scale-container {
        width: 100%;
        text-align: center;
        margin: 0;
        padding: 0;
    }

    .scale-points {
        display: flex;
        justify-content: space-between;
        margin: 0 12px;
        font-size: 22px;
        letter-spacing: 2px;
    }

    .point {
        user-select: none;
    }

    .point.selected {
        color: black;
        font-weight: bold;
    }

    .point.unselected {
        color: #BBBBBB;
    }

    </style>
    """, unsafe_allow_html=True)

    # ================================
    # Punkteskala-Funktion
    # ================================
    def point_scale(question, left_label, right_label, key, steps=10):

        st.write(question)

        # Startwert setzen
        current_value = st.session_state.get(key, int((steps + 1) / 2))

        # Unsichtbarer Slider, der den Wert speichert
        slider_val = st.slider(
            label="",
            min_value=1,
            max_value=steps,
            value=current_value,
            key=key,
            label_visibility="collapsed"
        )

        # Punkteskala rendern
        st.markdown('<div class="scale-container">', unsafe_allow_html=True)
        st.markdown('<div class="scale-points">', unsafe_allow_html=True)

        point_html = ""
        for i in range(1, steps + 1):
            if i == slider_val:
                css_class = "point selected"
                symbol = "●"
            else:
                css_class = "point unselected"
                symbol = "○"
            point_html += f'<span class="{css_class}">{symbol}</span>'

        st.markdown(point_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Beschriftungen links und rechts
        col_l, col_r = st.columns(2)
        with col_l:
            st.caption(f"1 = {left_label}")
        with col_r:
            st.caption(f"{steps} = {right_label}")

        st.markdown("")

        return slider_val

    # ================================
    # Beginn Fragebogen
    # ================================
    st.markdown("## 📋 Abschlussfragebogen zur Verhandlung")
    st.info("Bitte füllen Sie den Fragebogen aus. Ihre Antworten bleiben anonym.")
    st.markdown("---")

    # 1. Alter
    age = st.text_input("1. Wie alt sind Sie?")
    st.markdown("---")

    # 2. Geschlecht – responsive Grid
    st.write("2. Mit welchem Geschlecht identifizieren Sie sich?")

    gender_options = ["männlich", "weiblich", "divers", "keine Angabe"]

    st.markdown('<div class="gender-grid">', unsafe_allow_html=True)
    gender = st.radio("", gender_options, label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

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

    # 4. Fachbereich
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

    # 5. Zufriedenheit Ergebnis
    satisfaction_outcome = point_scale(
        "5. Wie zufrieden sind Sie mit dem Ergebnis der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        "s_outcome",
        steps=10
    )
    st.markdown("---")

    # 6. Zufriedenheit Verlauf
    satisfaction_process = point_scale(
        "6. Wie zufriedenstellend fanden Sie den Verlauf der Verhandlung?",
        "sehr unzufrieden",
        "sehr zufrieden",
        "s_process",
        steps=10
    )
    st.markdown("---")

    # 7. Preisliches Ergebnis
    better_result = point_scale(
        "7. Hätten Sie ein besseres preisliches Ergebnis erzielen können?",
        "keine preisliche Verbesserung",
        "viel bessere preisliche Verbesserung",
        "s_better",
        steps=10
    )
    st.markdown("---")

    # 8. Dominanzskala 1–5
    deviation = point_scale(
        "8. Wie dominant waren Sie im Vergleich zu Ihrem normalen Verhalten?",
        "stark nachgiebig",
        "stark dominant",
        "s_deviation",
        steps=5
    )
    st.markdown("---")

    # 9. Verhandlungsbereitschaft im Alltag
    willingness = point_scale(
        "9. Wie hoch ist Ihre Bereitschaft zu verhandeln im Alltag?",
        "ich verhandle nie",
        "ich verhandle fast immer",
        "s_willing",
        steps=10
    )
    st.markdown("---")

    # 10. Wiederverhandlung Ja/Nein
    st.write("10. Würden Sie erneut mit dem Bot verhandeln wollen?")
    again = st.radio("", ["Ja", "Nein"], horizontal=True)
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
