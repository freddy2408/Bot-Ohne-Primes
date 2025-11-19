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

# --------------------------------
# Session State initialisieren
# --------------------------------
if "session_id" not in st.session_state:
    st.session_state["session_id"] = f"sess-{int(time.time())}"

if "history" not in st.session_state:
    st.session_state["history"] = []  # Chat-Verlauf als Liste von Dicts

if "agreed_price" not in st.session_state:
    st.session_state["agreed_price"] = None  # Preis, der per Deal-Button bestätigt werden kann

if "closed" not in st.session_state:
    st.session_state["closed"] = False  # Ob die Verhandlung abgeschlossen ist

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

CHAT_CSS = """
<style>
section.main > div {padding-top: 1rem;}
.chat-bubble {padding:.7rem .9rem;border-radius:16px;margin:.25rem 0;line-height:1.4;display:inline-block;max-width:85%;box-shadow:0 1px 2px rgba(0,0,0,.06);}
.msg-user {background:#1C64F2;color:white;border-bottom-right-radius:4px;}
.msg-bot  {background:#F2F4F7;color:#0B1220;border-bottom-left-radius:4px;}
.msg-meta {font-size:.72rem;color:#667085;margin-top:.15rem;}
.row {display:flex;align-items:flex-end;margin:.25rem 0;}
.row.right {justify-content:flex-end;}
.row.left  {justify-content:flex-start;}
hr.soft {border:none;border-top:1px solid #EEE;margin:.75rem 0;}
div.block-container {padding-top:1.2rem;}
.stButton > button {border-radius:999px;padding:.6rem 1rem;font-weight:600;}
</style>
"""
st.markdown(CHAT_CSS, unsafe_allow_html=True)

# -----------------------------
# [EXPERIMENTSPARAMETER – defaults]
# -----------------------------
DEFAULT_PARAMS = {
    "scenario_text": "Sie verhandeln über ein neues iPad (neu, 256 GB, Space Grey) inklusive Apple Pencil (2. Gen) mit M5-Chip.",
    "list_price": 1000,          # Ausgangspreis
    "min_price": 800,            # Untergrenze
    "tone": "freundlich, respektvoll, auf Augenhöhe, sachlich",
    "max_sentences": 4,          # KI-Antwortlänge in Sätzen
}

# -----------------------------
# [SESSION PARAMS]
# -----------------------------
if "sid" not in st.session_state:
    st.session_state.sid = str(uuid.uuid4())
if "params" not in st.session_state:
    st.session_state.params = DEFAULT_PARAMS.copy()

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

PRICE_RE = re.compile(r"(?:€\s*)?(\d{2,5})")
def extract_prices(text: str):
    return [int(m.group(1)) for m in PRICE_RE.finditer(text)]

# -----------------------------
# [SYSTEM-PROMPT KONSTRUKTION – LLM EINBINDUNG]
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
        "Bei 700–799 €: kontere typischerweise mit 870–970 € (je nach Verhandlungston), und gehe erst mit der Zeit tiefer, Ziel soll am Ende immer noch eine Einigung sein. "
        f"Bei ≥ {params['min_price']} €: du kannst zustimmen, sofern sonst alles passt (Ort/Zahlung), oder minimal (5–20 €) höher kontern; unterschreite NIE {params['min_price']} €. "
        "Zum Gerät, falls gefragt: neu, 256 GB, Space Grey, Apple Pencil (2. Generation), M5-Chip."
    )

# -----------------------------
# [OPENAI: REST CALL + LLM-REPLY]
# -----------------------------
def call_openai(messages, temperature=0.3, max_tokens=240):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        st.error(f"Netzwerkfehler zur OpenAI-API: {e}")
        return None

    status = r.status_code
    text = r.text

    try:
        data = r.json()
    except Exception:
        data = None

    if status != 200:
        err_msg = None
        err_type = None
        if isinstance(data, dict):
            err = data.get("error") or {}
            err_msg = err.get("message")
            err_type = err.get("type")
        st.error(
            f"OpenAI-API-Fehler {status}"
            f"{' ('+err_type+')' if err_type else ''}"
            f": {err_msg or text[:500]}"
        )
        st.caption("Tipp: Prüfe MODEL / API-Key / Quota / Nachrichtenformat.")
        return None

    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        st.error("Antwortformat unerwartet. Rohdaten:")
        st.code(text[:1000])
        return None


def generate_reply(history, params: dict) -> str:
    """
    LLM-Antwort mit System-Prompt und Regelprüfung (Power-Primes, Preis-Floor).
    Wird im aktuellen UI nicht aufgerufen, bleibt aber als Einbindung bestehen.
    """
    sys_msg = {"role": "system", "content": system_prompt(params)}
    reply = call_openai([sys_msg] + history)
    if not isinstance(reply, str):
        return "Entschuldigung, gerade gab es ein technisches Problem. Bitte versuchen Sie es erneut."

    def violates_rules(text: str) -> str | None:
        if contains_power_primes(text):
            return "Keine Macht-/Knappheits-/Autoritäts-Frames verwenden."
        prices = extract_prices(text)
        if any(p < params["min_price"] for p in prices):
            return f"Unterschreite nie {params['min_price']} €; mache kein Angebot darunter."
        return None

    reason = violates_rules(reply)
    attempts = 0
    while reason and attempts < 2:
        attempts += 1
        history2 = [sys_msg] + history + [
            {"role": "system", "content": f"REGEL-VERSTOSS: {reason} Antworte neu – freundlich, verhandelnd, in {params['max_sentences']} Sätzen."}
        ]
        reply = call_openai(history2, temperature=0.25, max_tokens=220)
        reason = violates_rules(reply)

    if reason:
        prices = extract_prices(reply)
        low_prices = [p for p in prices if p < params["min_price"]]
        if low_prices:
            reply = re.sub(
                PRICE_RE,
                lambda m: m.group(0) if int(m.group(1)) >= params["min_price"] else str(params["min_price"]),
                reply,
            )
        for pat in BAD_PATTERNS:
            reply = re.sub(pat, "", reply, flags=re.IGNORECASE)

    return reply

# -----------------------------
# [EINFACHE, REGELBASIERTE BOT-LOGIK – wie zuvor]
# -----------------------------
def simple_negotiation_bot(user_msg: str, params: dict) -> tuple[str, int | None, bool]:
    """
    Gibt zurück: (bot_reply, proposed_price_or_None, ready_to_close?)
    - bot_reply: Text, den der Bot antwortet
    - proposed_price: Zahl in €, die als nächster Deal-Preis vorgeschlagen wird (oder None)
    - ready_to_close: True, wenn der Bot einer Einigung zugestimmt hat
    """
    txt = user_msg.lower().replace("€", "").replace("eur", "").strip()

    offered = None
    nums = re.findall(r"\d{2,4}", txt)
    if nums:
        try:
            offered = int(nums[0])
        except ValueError:
            offered = None

    # 1. Sehr niedriges Angebot (< 500 €) → unrealistisch
    if offered is not None and offered < 500:
        return (
            "Das liegt deutlich unter einem realistischen Preis. "
            "Bitte nenn mir ein realistischeres Angebot – das Gerät ist neu (256 GB, Space Grey) "
            "mit 256 GB Speicher sowie Apple Pencil (2. Generation) und M5-Chip.",
            None,
            False,
        )

    # 2. 500–699 € → Gegenangebot 880–920 €
    if offered is not None and 500 <= offered <= 699:
        return (
            "Danke für dein Angebot. Aufgrund des Neuzustands, 256 GB Speicher und Apple Pencil "
            "sehe ich uns eher bei 900 €. Könntest du auf 900 € gehen?",
            900,
            False,
        )

    # 3. 700–799 € → Gegenangebot leicht über Untergrenze
    if offered is not None and 700 <= offered <= 799:
        counter = max(params["min_price"] + 20, 830)  # bleibt über 800 €
        return (
            f"Wir sind schon recht nah beieinander. Ich könnte bei {counter} € entgegenkommen. "
            "Wäre das für dich in Ordnung?",
            counter,
            False,
        )

    # 4. Angebot ≥ Untergrenze → Zustimmung möglich
    if offered is not None and offered >= params["min_price"]:
        return (
            f"Einverstanden – {offered} € ist in Ordnung, sofern Abholung und Zahlung passen. "
            f"Wenn du auf »Deal bestätigen« klickst, halten wir {offered} € fest.",
            offered,
            True,
        )

    # 5. Kein konkretes Angebot → allgemeine Antwort
    return (
        "Hi! Ich biete ein neues iPad (256 GB, Space Grey) mit 256 GB Speicher, "
        "inklusive Apple Pencil (2. Generation) und M5-Chip an. "
        f"Der Ausgangspreis liegt bei {params['list_price']} €. Was schwebt dir preislich vor?",
        None,
        False,
    )

# -----------------------------
# [ERGEBNIS-LOGGING (SQLite)]
# -----------------------------
DB_PATH = "verhandlungsergebnisse.sqlite3"

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            session_id TEXT,
            deal INTEGER,
            price INTEGER,
            msg_count INTEGER
        )
    """)
    conn.commit()
    conn.close()

def log_result(session_id: str, deal: bool, price: int | None, msg_count: int):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO results (ts, session_id, deal, price, msg_count) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), session_id, 1 if deal else 0, price, msg_count),
    )
    conn.commit()
    conn.close()

def load_results_df() -> pd.DataFrame:
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT ts, session_id, deal, price, msg_count FROM results ORDER BY id DESC",
        conn,
    )
    conn.close()
    if df.empty:
        return df
    df["deal"] = df["deal"].map({1: "Deal", 0: "Abgebrochen"})
    return df

# -----------------------------
# [Szenario-Kopf]
# -----------------------------
with st.container():
    st.subheader("Szenario")
    st.write(st.session_state.params["scenario_text"])
    st.write(f"**Ausgangspreis:** {st.session_state.params['list_price']} €")

st.caption(f"Session-ID: `{st.session_state.sid}`")

# -----------------------------
# [CHAT-UI]
# -----------------------------
st.subheader("💬 iPad Verhandlungs-Bot")

# 1) Initiale Bot-Nachricht einmalig
if len(st.session_state["history"]) == 0:
    first_msg = (
        "Hi! Ich biete ein neues iPad (256 GB, Space Grey) inklusive Apple Pencil (2. Gen) "
        f"mit M5-Chip an. Der Ausgangspreis liegt bei {DEFAULT_PARAMS['list_price']} €. "
        "Was schwebt dir preislich vor?"
    )
    st.session_state["history"].append({
        "role": "assistant",
        "text": first_msg,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })

# 2) Chat-Verlauf anzeigen
for item in st.session_state["history"]:
    side = "right" if item["role"] == "user" else "left"
    klass = "msg-user" if item["role"] == "user" else "msg-bot"
    st.markdown(f"""
    <div class="row {side}">
        <div class="chat-bubble {klass}">{item['text']}</div>
    </div>
    <div class="row {side}"><div class="msg-meta">{item['ts']}</div></div>
    """, unsafe_allow_html=True)

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# 3) Chat-Eingabe (einmal)
user_input = st.chat_input(
    "Deine Nachricht",
    disabled=st.session_state["closed"],
)

# 4) Wenn User etwas sendet → Bot antwortet
if user_input and not st.session_state["closed"]:
    # Nutzer-Nachricht speichern
    st.session_state["history"].append({
        "role": "user",
        "text": user_input.strip(),
        "ts": datetime.now().isoformat(timespec="seconds"),
    })

    # Bot-Antwort – aktuell regelbasiert (Funktionsweise unverändert)
    # Wenn du später LLM nutzen willst: generate_reply(history_for_llm, st.session_state.params)
    reply, proposed_price, ready = simple_negotiation_bot(user_input, DEFAULT_PARAMS)

    st.session_state["history"].append({
        "role": "assistant",
        "text": reply,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })

    # Deal-Preis für Button merken
    if ready and proposed_price is not None:
        st.session_state["agreed_price"] = int(proposed_price)
    else:
        st.session_state["agreed_price"] = None

    st.experimental_rerun()

# 5) Deal bestätigen / Abbrechen
deal_col1, deal_col2 = st.columns([1, 1])
with deal_col1:
    show_deal = (
        st.session_state.get("agreed_price") is not None
        and not st.session_state.get("closed", False)
    )
    confirm = st.button(
        f"✅ Deal bestätigen: {st.session_state.get('agreed_price')} €",
        use_container_width=True,
    ) if show_deal else False

with deal_col2:
    cancel = st.button(
        "❌ Abbrechen",
        use_container_width=True,
    ) if not st.session_state.get("closed", False) else False

# 6) Abbrechen-Handler (weiter verhandeln erlaubt)
if cancel and not st.session_state.get("closed", False):
    st.session_state["agreed_price"] = None
    st.info("Deal abgebrochen. Du kannst weiter verhandeln.")
    st.experimental_rerun()

# 7) Deal-Bestätigung → Ergebnis speichern
if confirm and not st.session_state.get("closed", False) and st.session_state.get("agreed_price") is not None:
    st.session_state["closed"] = True
    msg_count = len([m for m in st.session_state.get("history", []) if m["role"] in ("user", "assistant")])
    log_result(st.session_state["session_id"], True, int(st.session_state["agreed_price"]), msg_count)
    st.success(f"Deal bestätigt: {st.session_state['agreed_price']} €. Die Verhandlung ist abgeschlossen.")
    st.stop()

# 8) Verhandlung ohne Einigung beenden
if not st.session_state.get("closed", False):
    no_deal = st.button("🔒 Verhandlung beenden (ohne Einigung)")
    if no_deal:
        st.session_state["closed"] = True
        msg_count = len([m for m in st.session_state.get("history", []) if m["role"] in ("user", "assistant")])
        log_result(st.session_state["session_id"], False, None, msg_count)
        st.info("Verhandlung beendet – ohne Einigung.")
        st.stop()

# -----------------------------
# [ADMIN-BEREICH: Ergebnisse (privat)]
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
            from io import BytesIO
            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                "Excel herunterladen",
                buffer,
                file_name="verhandlungsergebnisse.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
