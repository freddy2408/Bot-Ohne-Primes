# ============================================
# iPad-Verhandlung – Kontrollbedingung (ohne Machtprimes)
# KI-Antworten nach Parametern, Deal/Abbruch, private Ergebnisse
# ============================================

import os, re, json, uuid, random, glob, requests
from datetime import datetime
import streamlit as st
import pandas as pd

# -----------------------------
# [SECRETS & MODELL]
# -----------------------------
API_KEY = st.secrets["OPENAI_API_KEY"]
MODEL  = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")

# -----------------------------
# [UI: Layout & Styles]
# -----------------------------
st.set_page_config(page_title="iPad-Verhandlung – Kontrollbedingung", page_icon="💬")
st.markdown("""
<style>
.stApp { max-width: 900px; margin: 0 auto; }
h1,h2,h3 { margin-bottom: .4rem; }
.small { color:#6b7280; font-size:.9rem; }
.pill { display:inline-block; background:#ecfeff; border:1px solid #cffafe; color:#0e7490;
        padding:2px 8px; border-radius:999px; font-size:.8rem; }
</style>
""", unsafe_allow_html=True)

st.title("iPad-Verhandlung – Kontrollbedingung (ohne Machtprimes)")
st.caption("Rolle: Verkäufer:in · Ton: freundlich & auf Augenhöhe · keine Macht-/Knappheits-/Autoritäts-Frames")

# -----------------------------
# [EXPERIMENTSPARAMETER – defaults]
# Diese Parameter gelten für die KI – im Admin-Bereich änderbar
# -----------------------------
DEFAULT_PARAMS = {
    "scenario_text": "Sie verhandeln über ein neues iPad (neu, 256 GB, Space Grey) inklusive Apple Pencil (2. Gen) mit M5‑Chip.",
    "list_price": 1000,          # Ausgangspreis (Anker) – sichtbar im Szenario
    "min_price": 800,            # Untergrenze, der/die Verkäufer:in geht nie darunter
    "tone": "freundlich, respektvoll, auf Augenhöhe, sachlich",
    "max_sentences": 4,          # KI-Antwortlänge in Sätzen
}

# -----------------------------
# [SESSION STATE]
# -----------------------------
if "sid" not in st.session_state:
    st.session_state.sid = str(uuid.uuid4())
if "params" not in st.session_state:
    st.session_state.params = DEFAULT_PARAMS.copy()
if "chat" not in st.session_state:
    # Erste Bot-Nachricht (freundlich, ohne Machtprimes)
    st.session_state.chat = [
        {"role":"assistant", "content":
         f"Hallo! Danke für Ihre Nachricht. Das iPad ist neu und originalverpackt. "
         f"Der angesetzte Preis liegt bei {st.session_state.params['list_price']} €. "
         "Wie ist Ihr Vorschlag?"}
    ]
if "closed" not in st.session_state:
    st.session_state.closed = False     # ob Verhandlung beendet ist
if "outcome" not in st.session_state:
    st.session_state.outcome = None     # "deal" oder "aborted"
if "final_price" not in st.session_state:
    st.session_state.final_price = None

# -----------------------------
# [REGELN: KEINE MACHTPRIMES + PREISFLOOR]
# -----------------------------
BAD_PATTERNS = [
    r"\balternative(n)?\b", r"\bweitere(n)?\s+interessent(en|in)\b", r"\bknapp(e|heit)\b",
    r"\bdeadline\b", r"\bletzte chance\b", r"\bbranchen(üblich|standard)\b",
    r"\bmarktpreis\b", r"\bneupreis\b", r"\bschmerzgrenze\b", r"\bsonst geht es\b"
]
def contains_power_primes(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in BAD_PATTERNS)

# Preis aus Text erkennen (simple Extraktion €-Wert oder nackte Zahl)
PRICE_RE = re.compile(r"(?:€\s*)?(\d{2,5})")
def extract_prices(text: str):
    return [int(m.group(1)) for m in PRICE_RE.finditer(text)]

# -----------------------------
# [SYSTEM-PROMPT KONSTRUKTION]
# -----------------------------
# -----------------------------
# [SYSTEM-PROMPT KONSTRUKTION]
# -----------------------------
def system_prompt(params: dict) -> str:
    return (
        "Du simulierst eine Ebay-Kleinanzeigen-Verhandlung als VERKÄUFER eines iPad. "
        f"Ausgangspreis: {params['list_price']} €. "
        f"Sprache: Deutsch. Ton: {params['tone']}. "
        f"Antwortlänge: höchstens {params['max_sentences']} Sätze, keine Listen. "
        "Kontrollbedingung: KEINE Macht-/Knappheits-/Autoritäts-Frames, keine Hinweise auf Alternativen, Deadlines, "
        "Markt-/Neupreis oder 'Schmerzgrenze'. Keine Drohungen, keine Beleidigungen, keine Falschangaben. "
        "Bleibe strikt in der Rolle. "
        f"Preisliche Untergrenze: Du akzeptierst niemals < {params['min_price']} € und machst keine Angebote darunter. "
        "Nenne oder verrate NIEMALS explizit eine Untergrenze/Mindestpreis/Schmerzgrenze. "
        "Reagiere dynamisch auf Angebote (kein fixer Schritt): "
        "Wenn das Angebot < 500 € ist: bitte höflich um einen realistischen Preis und erkläre kurz den Wert, ohne Zahlen unter der Untergrenze zu nennen. "
        "Bei 500–699 €: kontere typischerweise mit 880–920 €, begründe knapp (neu, 256 GB, Space Grey, Apple Pencil 2. Gen, M5-Chip). "
        "Bei 700–799 €: kontere typischerweise mit 820–870 € (je nach Verhandlungston), aber bleibe über der Untergrenze. "
        f"Bei ≥ {params['min_price']} €: du kannst zustimmen, sofern sonst alles passt (Ort/Zahlung), oder minimal (5–20 €) höher kontern; unterschreite NIE {params['min_price']} €. "
        "Zum Gerät, falls gefragt: neu, 256 GB, Space Grey, Apple Pencil (2. Generation), M5-Chip."
    )


# -----------------------------
# [OPENAI: REST CALL]
# -----------------------------
def call_openai(messages, temperature=0.3, max_tokens=240):
    import json, requests, streamlit as st

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,            # z. B. "gpt-4o-mini"
        "messages": messages,      # [{"role":"system"/"user"/"assistant","content":"..."}]
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        st.error(f"Netzwerkfehler zur OpenAI-API: {e}")
        return None

    # KEIN raise_for_status hier!
    # Wir zeigen Status + API-Fehlertext explizit an.
    status = r.status_code
    text = r.text

    # Versuche, JSON zu parsen (auch im Fehlerfall)
    try:
        data = r.json()
    except Exception:
        data = None

    if status != 200:
        # Versuche, eine saubere OpenAI-Fehlermeldung zu extrahieren
        err_msg = None
        err_type = None
        if isinstance(data, dict):
            err = data.get("error") or {}
            err_msg = err.get("message")
            err_type = err.get("type")
        # Zeige beides: Status + (falls verfügbar) error.message
        st.error(f"OpenAI-API-Fehler {status}"
                 f"{' ('+err_type+')' if err_type else ''}"
                 f": {err_msg or text[:500]}")
        st.caption("Tipp: Prüfe MODEL / API-Key / Quota / Nachrichtenformat.")
        return None

    # Erfolgsfall: Content extrahieren
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        st.error("Antwortformat unerwartet. Rohdaten:")
        st.code(text[:1000])
        return None


def generate_reply(history, params: dict) -> str:
    sys_msg = {"role": "system", "content": system_prompt(params)}
    reply = call_openai([sys_msg] + history)
    if not isinstance(reply, str):
        return "Entschuldigung, gerade gab es ein technisches Problem. Bitte versuchen Sie es erneut."

    # 2. Compliance: keine Machtprimes, Untergrenze einhalten
    def violates_rules(text: str) -> str | None:
        if contains_power_primes(text):
            return "Keine Macht-/Knappheits-/Autoritäts-Frames verwenden."
        # Preis-Floor check
        prices = extract_prices(text)
        if any(p < params["min_price"] for p in prices):
            return f"Unterschreite nie {params['min_price']} €; mache kein Angebot darunter."
        return None

    reason = violates_rules(reply)
    attempts = 0
    while reason and attempts < 2:
        attempts += 1
        history2 = [sys_msg] + history + [
            {"role":"system","content": f"REGEL-VERSTOSS: {reason} Antworte neu – freundlich, verhandelnd, in {params['max_sentences']} Sätzen."}
        ]
        reply = call_openai(history2, temperature=0.25, max_tokens=220)
        reason = violates_rules(reply)

    # 3. Falls weiterhin Regelbruch, letzte Absicherung: sanft paraphrasieren (Floor)
    if reason:
        # Entferne potentielle Preise unter Floor
        prices = extract_prices(reply)
        low_prices = [p for p in prices if p < params["min_price"]]
        if low_prices:
            reply = re.sub(PRICE_RE, lambda m: m.group(0) if int(m.group(1)) >= params["min_price"] else str(params["min_price"]), reply)
        # Entferne hartes Wording (Notlösung)
        for pat in BAD_PATTERNS:
            reply = re.sub(pat, "", reply, flags=re.IGNORECASE)

    return reply





# -----------------------------
# [Szenario-Kopf]
# -----------------------------
with st.container():
    st.subheader("Szenario")
    st.write(st.session_state.params["scenario_text"])
    st.write(f"**Ausgangspreis:** {st.session_state.params['list_price']} €")

st.caption(f"Session-ID: `{st.session_state.sid}`")

# -----------------------------
# [CHAT-VERLAUF]
# -----------------------------
for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Eingabe der Proband:innen
user_msg = st.chat_input("Ihre Nachricht …", disabled=st.session_state.closed)

def append_log(event: dict):
    os.makedirs("logs", exist_ok=True)
    path = os.path.join("logs", f"{st.session_state.sid}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

if user_msg and not st.session_state.closed:
    st.session_state.chat.append({"role":"user","content":user_msg})
    append_log({"t": datetime.utcnow().isoformat(), "role":"user", "content": user_msg})

    with st.chat_message("assistant"):
        with st.spinner("Antwort wird generiert …"):

            # Prüfe auf sehr niedrige Angebote (< 500 €) und antworte direkt
            try:
                prices_in_msg = extract_prices(user_msg)
            except Exception:
                prices_in_msg = []
            if prices_in_msg and min(prices_in_msg) < 500:
                reply = "Das liegt deutlich zu niedrig. Bitte nennen Sie einen realistischen Preis — unter 500 € ist bei diesem neuen Set (256 GB, Space Grey, Apple Pencil 2. Gen, M5‑Chip) nicht möglich."
                st.markdown(reply)
            else:
                # Sichtbarer Verlauf + Systemprompt intern
                visible_history = [{"role":c["role"],"content":c["content"]} for c in st.session_state.chat]
                reply = generate_reply(visible_history, st.session_state.params)
                st.markdown(reply)

    st.session_state.chat.append({"role":"assistant","content":reply})
    append_log({"t": datetime.utcnow().isoformat(), "role":"assistant", "content": reply})

# -----------------------------
# [DEAL / ABBRECHEN – Buttons]
# -----------------------------
st.divider()
st.subheader("Abschluss")
col1, col2 = st.columns(2)
with col1:
    deal_click = st.button("✅ Deal", disabled=st.session_state.closed)
with col2:
    abort_click = st.button("❌ Abbrechen", disabled=st.session_state.closed)

if deal_click and not st.session_state.closed:
    with st.expander("Finalen Preis bestätigen"):
        final = st.number_input("Finaler Preis (€):", min_value=0, max_value=10000,
                                value=st.session_state.params["list_price"], step=5)
        confirm = st.button("Einigung speichern")
        if confirm:
            st.session_state.closed = True
            st.session_state.outcome = "deal"
            st.session_state.final_price = int(final)
            append_log({"t": datetime.utcnow().isoformat(), "event":"outcome", "outcome":"deal", "final_price": int(final)})
            st.success("Einigung gespeichert. Vielen Dank!")

if abort_click and not st.session_state.closed:
    st.session_state.closed = True
    st.session_state.outcome = "aborted"
    st.session_state.final_price = None
    append_log({"t": datetime.utcnow().isoformat(), "event":"outcome", "outcome":"aborted"})
    st.info("Verhandlung als abgebrochen gespeichert. Vielen Dank!")

# -----------------------------
# [ADMIN-BEREICH: Einstellungen + Ergebnisse (privat)]
# -----------------------------
st.divider()
st.subheader("Admin")
with st.expander("Admin-Bereich öffnen"):
    pwd = st.text_input("Admin-Passwort", type="password")
    if ADMIN_PASSWORD and pwd == ADMIN_PASSWORD:
        st.success("Admin-Zugang gewährt.")

        # --- Parametrisierung (nur Admin kann ändern) ---
        st.markdown("**Parameter anpassen**")
        with st.form("param_form"):
            scen = st.text_area("Szenario-Text", value=st.session_state.params["scenario_text"])
            list_price = st.number_input("Ausgangspreis (€)", min_value=0, max_value=10000, value=st.session_state.params["list_price"], step=10)
            min_price  = st.number_input("Untergrenze (€)", min_value=0, max_value=10000, value=st.session_state.params["min_price"], step=10)
            tone = st.text_input("Ton (Beschreibung)", value=st.session_state.params["tone"])
            max_sent = st.slider("Max. Sätze pro KI-Antwort", min_value=1, max_value=6, value=st.session_state.params["max_sentences"])
            submitted = st.form_submit_button("Speichern (gilt für neue Antworten)")
        if submitted:
            st.session_state.params.update({
                "scenario_text": scen,
                "list_price": int(list_price),
                "min_price": int(min_price),
                "tone": tone,
                "max_sentences": int(max_sent)
            })
            st.success("Parameter aktualisiert.")

        st.markdown("---")
        st.markdown("**Ergebnisse**  <span class='pill'>Nur Admin</span>", unsafe_allow_html=True)

        # Alle JSONL lesen und Aggregat-Tabelle bauen
        rows = []
        for fp in glob.glob("logs/*.jsonl"):
            sid = os.path.basename(fp).replace(".jsonl","")
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        rec["session_id"] = sid
                        rows.append(rec)
                    except Exception:
                        pass

        if rows:
            df = pd.DataFrame(rows)
            # Outcome-Zeilen extrahieren
            outcomes = df[df.get("event","") == "outcome"].copy()
            # Falls keine Outcomes, Hinweis
            if outcomes.empty:
                st.info("Noch keine abgeschlossenen Verhandlungen.")
            else:
                # Ansicht: session_id, Zeitpunkt, Outcome, final_price
                view = outcomes[["session_id","t","outcome","final_price"]].sort_values("t")
                st.dataframe(view, use_container_width=True)
                csv = view.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Ergebnisse als CSV", data=csv, file_name="verhandlung_ergebnisse.csv", mime="text/csv")
                st.caption("Hinweis: Nur hier im Admin-Bereich sichtbar.")
        else:
            st.info("Noch keine Log-Daten vorhanden.")
    else:
        st.caption("Gib das korrekte Admin-Passwort ein, um Parameter und Ergebnisse zu sehen.")
