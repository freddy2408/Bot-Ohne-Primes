# ============================================
# iPad-Verhandlung – Kontrollbedingung (ohne Machtprimes)
# KI-Antworten nach Parametern, Deal/Abbruch, private Ergebnisse
# ============================================

import os, re, json, uuid, random, glob, requests
from datetime import datetime
import streamlit as st
import pandas as pd
import time
import sqlite3

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
# --- Session State sicher initialisieren (direkt nach den Imports einfügen) ---
def init_state():
    ss = st.session_state
    ss.setdefault("session_id", f"sess-{int(time.time())}")
    ss.setdefault("history", [])        # Chat-Verlauf
    ss.setdefault("agreed_price", None) # zuletzt verhandelter Preis für Deal-Button
    ss.setdefault("closed", False)      # Verhandlung abgeschlossen?

init_state()

st.title("💬 iPad Verhandlungs-Bot")

if len(st.session_state.get("history", [])) == 0:
    # initiale Bot-Nachricht (LLM oder simple_negotiation_bot)
    first_msg = "Hi! Ich biete ein neues iPad (256 GB, Space Grey) inklusive Apple Pencil (2. Gen) mit M5-Chip an. "\
                f"Der Ausgangspreis liegt bei {DEFAULT_PARAMS['list_price']} €. Was schwebt dir preislich vor?"
    st.session_state.history.append({"role":"assistant","text":first_msg,"ts":datetime.now().isoformat(timespec="seconds")})

for item in st.session_state.get("history", []):
    side = "right" if item["role"] == "user" else "left"
    klass = "msg-user" if item["role"] == "user" else "msg-bot"
    st.markdown(f"""
    <div class="row {side}">
        <div class="chat-bubble {klass}">{item['text']}</div>
    </div>
    <div class="row {side}"><div class="msg-meta">{item['ts']}</div></div>
    """, unsafe_allow_html=True)

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

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
st.sidebar.header("📊 Ergebnisse")
pwd_ok = False
dashboard_password = st.secrets.get("DASHBOARD_PASSWORD", os.environ.get("DASHBOARD_PASSWORD"))
pwd_input = st.sidebar.text_input("Passwort für Dashboard", type="password")
if dashboard_password:
    if pwd_input and pwd_input == dashboard_password:
        pwd_ok = True
    elif pwd_input and pwd_input != dashboard_password:
        st.sidebar.warning("Falsches Passwort.")
else:
    st.sidebar.info("Kein Passwort gesetzt (DASHBOARD_PASSWORD). Dashboard ist deaktiviert.")

if pwd_ok:
    st.sidebar.success("Zugang gewährt.")
    with st.sidebar.expander("Alle Verhandlungsergebnisse", expanded=True):
        df = load_results_df()
        if len(df) == 0:
            st.write("Noch keine Ergebnisse gespeichert.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                "Excel herunterladen",
                buffer,
                file_name=f"verhandlungsergebnisse_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
