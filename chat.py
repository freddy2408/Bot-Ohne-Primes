
import os
import time
import sqlite3
from datetime import datetime
from io import BytesIO

import streamlit as st
import pandas as pd

# -----------------------------
# App Config & Styles
# -----------------------------
st.set_page_config(page_title="iPad Verhandlungs-Bot", page_icon="💬", layout="centered")

CHAT_CSS = """
<style>
/* overall page */
section.main > div {padding-top: 1rem;}
/* chat container */
.chat-bubble {
  padding: .7rem .9rem;
  border-radius: 16px;
  margin: .25rem 0 .25rem 0;
  line-height: 1.4;
  display: inline-block;
  max-width: 85%;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}
.msg-user { background: #1C64F2; color: white; border-bottom-right-radius: 4px; }
.msg-bot  { background: #F2F4F7; color: #0B1220; border-bottom-left-radius: 4px; }
.msg-meta { font-size: .72rem; color: #667085; margin-top: .15rem; }
.row { display: flex; align-items: flex-end; margin: .25rem 0; }
.row.right { justify-content: flex-end; }
.row.left  { justify-content: flex-start; }
hr.soft { border: none; border-top: 1px solid #EEE; margin: .75rem 0; }
div.block-container {padding-top: 1.2rem;}
/* buttons */
.stButton > button {border-radius: 999px; padding: .6rem 1rem; font-weight: 600;}
/* hide Streamlit chrome a bit for clean look */
footer {visibility: hidden;}
header {visibility: visible;}
"""
st.markdown(CHAT_CSS, unsafe_allow_html=True)

# -----------------------------
# Parameters
# -----------------------------
DEFAULT_PARAMS = {
    "list_price": 1000,
    "min_price": 800,  # Hardcap/Floor
    "tone": "freundlich, klar, bestimmt",
    "max_sentences": 3,
}

# -----------------------------
# Data Storage (SQLite) for results
# -----------------------------
DB_PATH = os.environ.get("NEGOTIATION_DB_PATH", "negotiations.db")

def _get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          session_id TEXT NOT NULL,
          agreed INTEGER NOT NULL,
          price INTEGER,
          msg_count INTEGER NOT NULL
        )
    """)
    conn.commit()
    return conn

DB = _get_db()

def log_result(session_id: str, agreed: bool, price: int | None, msg_count: int):
    DB.execute(
        "INSERT INTO results (created_at, session_id, agreed, price, msg_count) VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(timespec="seconds"), session_id, 1 if agreed else 0, price, msg_count)
    )
    DB.commit()

def load_results_df() -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM results ORDER BY id DESC", DB)
    # nicer columns
    if len(df) > 0:
        df = df.rename(columns={
            "created_at": "Zeitpunkt (UTC)",
            "session_id": "Session",
            "agreed": "Einigung?",
            "price": "Preis (€)",
            "msg_count": "Nachrichten gesamt"
        })
        df["Einigung?"] = df["Einigung?"].map({0:"Nein",1:"Ja"})
    return df

# -----------------------------
# Negotiation Logic (very simple placeholder LLM)
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

def simple_negotiation_bot(user_msg: str, params: dict) -> tuple[str, int | None, bool]:
    """
    Returns: (bot_reply, proposed_price_or_None, ready_to_close?)
    This is a simple rule-based stand-in for your LLM call. Plug your LLM where this returns.
    """
    txt = user_msg.lower().replace("€","").replace("eur","").strip()
    offered = None
    # naive number extraction
    import re
    nums = re.findall(r"\d{2,4}", txt)
    if nums:
        try:
            offered = int(nums[0])
        except:
            offered = None

    # lowball guard
    if offered is not None and offered < 500:
        return ("Das liegt deutlich unter einem realistischen Preis. "
                "Bitte nenn mir ein realistischeres Angebot – das Gerät ist neu (256 GB, Space Grey) mit Apple Pencil (2. Gen) und M5‑Chip.", None, False)

    # dynamic counters
    if offered is not None and 500 <= offered <= 699:
        return ("Danke für das Angebot. Aufgrund des Zustands und Zubehörs sehe ich uns eher bei 900 €. "
                "Könntest du auf 900 € gehen?", 900, False)

    if offered is not None and 700 <= offered <= 799:
        # stay > min_price
        counter = max(params["min_price"] + 20, 830)
        return (f"Wir sind nah beieinander. Ich könnte bei {counter} € entgegenkommen. "
                "Passt das für dich?", counter, False)

    if offered is not None and offered >= params["min_price"]:
        # can accept
        return (f"Einverstanden – {offered} € ist in Ordnung, sofern Abholung und Zahlung passen. "
                "Wenn du auf »Deal« bestätigst, halten wir {offered} € fest.", offered, True)

    # general response
    return ("Hi! Ich biete ein neues iPad (256 GB, Space Grey) inklusive Apple Pencil (2. Gen) mit M5‑Chip an. "
            f"Der Ausgangspreis liegt bei {params['list_price']} €. Was schwebt dir preislich vor?", None, False)

# -----------------------------
# Session State
# -----------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess-{int(time.time())}"
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {"role": "user"/"assistant", "text": "...", "ts": iso}
if "agreed_price" not in st.session_state:
    st.session_state.agreed_price = None
if "closed" not in st.session_state:
    st.session_state.closed = False

# -----------------------------
# Sidebar: Results Dashboard (password protected)
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

            # Excel download
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

# -----------------------------
# Main: Clean Chat UI
# -----------------------------
st.title("💬 iPad Verhandlungs‑Bot")

# initial assistant message (only once)
if len(st.session_state.history) == 0:
    first_msg = simple_negotiation_bot("", DEFAULT_PARAMS)[0]
    st.session_state.history.append({"role":"assistant","text":first_msg,"ts":datetime.now().isoformat(timespec="seconds")})

# render chat history
for item in st.session_state.history:
    side = "right" if item["role"] == "user" else "left"
    klass = "msg-user" if item["role"] == "user" else "msg-bot"
    with st.container():
        st.markdown(f"""
        <div class="row {side}">
            <div class="chat-bubble {klass}">{item['text']}</div>
        </div>
        <div class="row {side}"><div class="msg-meta">{item['ts']}</div></div>
        """, unsafe_allow_html=True)

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

col1, col2 = st.columns([3,1])

# input is disabled when closed
with col1:
    user_input = st.text_input("Deine Nachricht", placeholder="z. B. 'Würde 750 € bieten.'", disabled=st.session_state.closed)

with col2:
    send_clicked = st.button("Senden", use_container_width=True)

# "Deal bestätigen" button shows only when ready + not closed
deal_col1, deal_col2 = st.columns([1,1])
with deal_col1:
    show_deal = st.session_state.agreed_price is not None and not st.session_state.closed
    if show_deal:
        confirm = st.button(f"✅ Deal bestätigen: {st.session_state.agreed_price} €", use_container_width=True)
    else:
        confirm = False
with deal_col2:
    if not st.session_state.closed:
        cancel = st.button("❌ Abbrechen", use_container_width=True)
    else:
        cancel = False

# handle chat send
if send_clicked and user_input.strip() and not st.session_state.closed:
    st.session_state.history.append({"role":"user","text":user_input.strip(), "ts":datetime.now().isoformat(timespec="seconds")})
    reply, proposed_price, ready = simple_negotiation_bot(user_input, DEFAULT_PARAMS)
    st.session_state.history.append({"role":"assistant","text":reply, "ts":datetime.now().isoformat(timespec="seconds")})
    if ready and proposed_price is not None:
        st.session_state.agreed_price = int(proposed_price)
    else:
        st.session_state.agreed_price = None
    st.experimental_rerun()

# handle cancel
if cancel and not st.session_state.closed:
    st.session_state.agreed_price = None
    st.info("Deal abgebrochen. Du kannst weiter verhandeln.")
    st.experimental_rerun()

# handle Deal confirmation (no manual price entry)
if confirm and not st.session_state.closed and st.session_state.agreed_price is not None:
    st.session_state.closed = True
    # persist result
    msg_count = len([m for m in st.session_state.history if m["role"] in ("user","assistant")])
    log_result(st.session_state.session_id, True, st.session_state.agreed_price, msg_count)
    # Show final system message
    st.success(f"Deal bestätigt: {st.session_state.agreed_price} €. Die Verhandlung ist abgeschlossen.")
    st.stop()

# if closed without agreement, allow logging via button
if not st.session_state.closed:
    no_deal = st.button("🔒 Verhandlung beenden (ohne Einigung)")
    if no_deal:
        st.session_state.closed = True
        msg_count = len([m for m in st.session_state.history if m["role"] in ("user","assistant")])
        log_result(st.session_state.session_id, False, None, msg_count)
        st.info("Verhandlung beendet – ohne Einigung.")
        st.stop()
