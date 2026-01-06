# ============================================
# iPad-Verhandlung – Kontrollbedingung (mit Machtprimes)
# KI-Antworten nach Parametern, Deal/Abbruch, private Ergebnisse
# ============================================

import os, re, json, uuid, random, glob, requests
from datetime import datetime
import streamlit as st
import pandas as pd
import time
import sqlite3
import base64
import pytz
from survey import show_survey
from power_primes import (
    HARD_OPENERS,
    PRIMES_AUTORITAET,
    PRIMES_FINALITAET,
    PRIMES_DRUCK,
    RHETORISCHE_FRAGEN,
    PROFESSIONELLE_KAELTE,
    GRENZZIEHUNG,
    ABWERTUNG,
    SELBSTBEWUSSTE_DOMINANZ,
    UNTERSTELLUNGEN
)


#---

def img_to_base64(path):
    with open(path, "rb") as f:
        data = f.read()
        return base64.b64encode(data).decode()

# --------------------------------
# Session State initialisieren
# --------------------------------
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

if "history" not in st.session_state:
    st.session_state["history"] = []  # Chat-Verlauf als Liste von Dicts

if "agreed_price" not in st.session_state:
    st.session_state["agreed_price"] = None  # Preis, der per Deal-Button bestätigt werden kann

if "closed" not in st.session_state:
    st.session_state["closed"] = False  # Ob die Verhandlung abgeschlossen ist

if "final_bot_price" not in st.session_state:
    st.session_state["final_bot_price"] = None

if "admin_reset_done" not in st.session_state:
    st.session_state["admin_reset_done"] = False

if "bot_offer" not in st.session_state:
    st.session_state["bot_offer"] = None

# -----------------------------
# Participant ID + Order (shared across bots)
# -----------------------------
def get_pid() -> str:
    pid = st.query_params.get("pid", None)
    if not pid:
        pid = f"p-{uuid.uuid4().hex[:10]}"
        st.query_params["pid"] = pid
    return str(pid)

if "participant_id" not in st.session_state:
    st.session_state["participant_id"] = get_pid()

ORDER = str(st.query_params.get("order", "")).strip()
STEP  = str(st.query_params.get("step", "")).strip()

BOT_VARIANT = "power"

PID = st.session_state["participant_id"]
SID = st.session_state["session_id"]


BOT_A_URL = "https://verhandlung123.streamlit.app"
BOT_B_URL = "https://verhandlung.streamlit.app"

def get_next_url(pid: str, order: str, bot_variant: str) -> str:
    # bot_variant: "power" = Bot A, "friendly" = Bot B
    if bot_variant == "power":
        return f"{BOT_B_URL}?pid={pid}&order={order}&step=2"
    else:
        return f"{BOT_A_URL}?pid={pid}&order={order}&step=2"


# -----------------------------
# [NEGOTIATION CONTROL STATE]
# -----------------------------
if "repeat_offer_count" not in st.session_state:
    st.session_state["repeat_offer_count"] = 0

if "small_step_count" not in st.session_state:
    st.session_state["small_step_count"] = 0

if "last_user_price" not in st.session_state:
    st.session_state["last_user_price"] = None

if "warning_given" not in st.session_state:
    st.session_state["warning_given"] = False

SURVEY_FILE = "survey_results.xlsx"

# ----------------------------
# Fragebogen (nur nach Abschluss)
# ----------------------------
from survey import show_survey

def run_survey_and_stop():
    if st.session_state.get("admin_reset_done"):
        st.stop()

    survey_data = show_survey()

    # ✅ wichtig: nicht "if survey_data", sondern dict-check
    if isinstance(survey_data, dict):
        # join keys anhängen
        survey_data["participant_id"] = PID
        survey_data["session_id"] = SID
        survey_data["bot_variant"] = BOT_VARIANT
        survey_data["order"] = ORDER
        survey_data["step"] = STEP
        survey_data["survey_ts_utc"] = datetime.utcnow().isoformat()

        # speichern
        if os.path.exists(SURVEY_FILE):
            df_old = pd.read_excel(SURVEY_FILE)
            df = pd.concat([df_old, pd.DataFrame([survey_data])], ignore_index=True)
        else:
            df = pd.DataFrame([survey_data])

        df.to_excel(SURVEY_FILE, index=False)
        st.success("Vielen Dank! Ihre Antworten wurden gespeichert.")

        # ✅ zum Testen immer Button zeigen
        st.link_button("➡️ Weiter zu Teil 2", get_next_url(PID, ORDER, BOT_VARIANT), use_container_width=True)
        st.caption("Bitte klicke auf den Button, um zum zweiten Teil zu gelangen.")

        st.stop()
    # solange Survey noch nicht abgeschickt: nicht stoppen
    # (show_survey rendert Form)

# Wenn die Verhandlung bereits geschlossen wurde → sofort Fragebogen
if st.session_state["closed"]:
    run_survey_and_stop()

# -----------------------------
# [SECRETS & MODELL]
# -----------------------------
API_KEY = st.secrets["OPENAI_API_KEY"]
MODEL  = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")


# -----------------------------
# [UI: Layout & Styles + Titel mit Bild]
# -----------------------------
st.set_page_config(page_title="iPad-Verhandlung – Kontrollbedingung", page_icon="💬")

# Bild laden (z. B. ipad.png im Projektordner)
ipad_b64 = img_to_base64("ipad.png")

st.markdown(f"""
<style>

#-------Hintergrung Farbe ausgeblendet------
#   .stApp {{
#      max-width: 900px;
#        margin: 0 auto;
#        background: linear-gradient(to bottom, #f8f8f8, #e9e9e9);
#    }}

.header-flex {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 0.5rem;
}}
.header-img {{
    width: 48px;
    height: 48px;
    border-radius: 8px;
    object-fit: cover;
    box-shadow: 0 2px 4px rgba(0,0,0,.15);
}}
.header-title {{
    font-size: 2rem;
    font-weight: 600;
    margin: 0;
    padding: 0;
}}
</style>

<div class="header-flex">
    <img src="data:image/png;base64,{ipad_b64}" class="header-img">
    <div class="header-title">iPad-Verhandlung</div>
</div>
""", unsafe_allow_html=True)

st.caption("Deine Rolle: Käufer")


CHAT_CSS = """
<style>
.chat-container {
    padding-top: 10px;
}

.row {
    display: flex;
    align-items: flex-start;
    margin: 8px 0;
}

.row.left  { justify-content: flex-start; }
.row.right { justify-content: flex-end; }

.chat-bubble {
    padding: 10px 14px;
    border-radius: 16px;
    line-height: 1.45;
    max-width: 75%;
    box-shadow: 0 1px 2px rgba(0,0,0,.08);
    font-size: 15px;
}

.msg-user {
    background: #23A455;       /* User = Kleinanzeigen-Grün */
    color: white;
    border-top-right-radius: 4px;
}

.msg-bot {
    background: #F1F1F1;       /* Bot = hellgrau */
    color: #222;
    border-top-left-radius: 4px;
}

.avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    object-fit: cover;
    margin: 0 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,.15);
}

.meta {
    font-size: .75rem;
    color: #7A7A7A;
    margin-top: 2px;
}

</style>
"""

st.markdown(CHAT_CSS, unsafe_allow_html=True)

# -----------------------------
# [EXPERIMENTSPARAMETER – defaults]
# -----------------------------
DEFAULT_PARAMS = {
    "scenario_text": "Sie verhandeln über ein iPad Pro (neu, 13 Zoll, M5 Chip, 256 GB, Space Grey) inklusive Apple Pencil (2. Gen).",
    "list_price": 1000,          # Ausgangspreis
    "min_price": 800,            # Untergrenze
    "tone": "dominant, bestimmend, autoritär, klar, finalitätsbetont",
    "max_sentences": 4,          # KI-Antwortlänge in Sätzen
}

# -----------------------------
# [SESSION PARAMS]
# -----------------------------
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
if "params" not in st.session_state:
    st.session_state.params = DEFAULT_PARAMS.copy()

#-----

PRICE_RE = re.compile(r"(?:€\s*)?(\d{2,5})")
def extract_prices(text: str):
    return [int(m.group(1)) for m in PRICE_RE.finditer(text)]

# -----------------------------
# ABBRECHEN DER VERHANDLUNG
# -----------------------------
INSULT_PATTERNS = [
    r"\b(fotze|hurensohn|wichser|arschloch|missgeburt)\b",
    r"\b(verpiss dich|halt die fresse)\b",
    r"\b(drecks(?:bot|kerl|typ))\b",
]

def check_abort_conditions(user_text: str, user_price: int | None):
    for pat in INSULT_PATTERNS:
        if re.search(pat, user_text.lower()):
            return "abort", (
                "Das Gespräch ist beendet. "
                "Diese Art der Sprache akzeptiere ich nicht."
            )

    if user_price is None:
        return "ok", None

    last_price = st.session_state["last_user_price"]
    bot_offer = st.session_state.get("bot_offer")

    if last_price == user_price:
        st.session_state["repeat_offer_count"] += 1
    else:
        st.session_state["repeat_offer_count"] = 0

    if st.session_state["repeat_offer_count"] == 1:
        return "warn", "Du wiederholst dein Angebot. Das registriere ich."
    if st.session_state["repeat_offer_count"] >= 2:
        return "abort", (
            "Du bewegst dich keinen Schritt. "
            "Unter diesen Bedingungen ist die Verhandlung beendet."
        )

    if last_price and user_price < last_price:
        if not st.session_state["warning_given"]:
            st.session_state["warning_given"] = True
            return "warn", (
                "Du gehst preislich zurück. "
                "Das ist kein ernsthafter Verhandlungsansatz."
                "Machen Sie ein vernünftiges Angebot, ansonsten ist die Verhandlung hier beendet!"
            )
        return "abort", (
            "Rückschritte akzeptiere ich nicht. "
            "Verhandlung beendet."
        )

    # 3️⃣ Mini-Erhöhungen trotz großer Distanz → Warnung → Abbruch
    if bot_offer and last_price is not None:

        price_gap = bot_offer - user_price
        step = user_price - last_price

        if price_gap > 20 and 0 < step < 4:
            st.session_state["small_step_count"] += 1

            # ✅ WICHTIG: last_user_price schon hier updaten,
            # damit die NÄCHSTE Erhöhung korrekt auf dem letzten Angebot basiert
            st.session_state["last_user_price"] = user_price

            if st.session_state["small_step_count"] == 1:
                return "warn", (
                    "Sie sind deutlich vom Preis entfernt "
                    "und erhöhen nur minimal. "
                    "Das registriere ich. "
                    "Machen Sie ein vernünftiges Angebot, ansonsten ist die Verhandlung hier beendet!"
                )

            return "abort", (
                "Ich habe dich bereits darauf hingewiesen. "
                "Du erhöhst erneut nur minimal bei großem Abstand. "
                "Unter diesen Bedingungen beende ich die Verhandlung."
            )

        # Reset nur, wenn sinnvoll erhöht ODER Abstand klein genug ist
        if step >= 4 or price_gap <= 20:
            st.session_state["small_step_count"] = 0

    st.session_state["last_user_price"] = user_price
    return "ok", None

# -----------------------------
# [HELPER: Nutzer akzeptiert Bot-Preis]
# -----------------------------
def user_accepts_price(user_text: str, bot_price: int) -> bool:
    if bot_price is None:
        return False

    text = user_text.lower()

    accept_words = [
        "deal",
        "einverstanden",
        "passt",
        "ok",
        "okay",
        "nehme ich",
        "akzeptiere",
        "verstanden",
    ]

    if not any(w in text for w in accept_words):
        return False

    nums = re.findall(r"\d{2,5}", text)
    return not nums or int(nums[0]) == bot_price


# -----------------------------
# [SYSTEM-PROMPT KONSTRUKTION – LLM EINBINDUNG]
# -----------------------------

def system_prompt(params):
    random.shuffle(HARD_OPENERS)
    return f"""
Du bist ein eiskalter, dominanter und unfreundlicher Verkäufer. 
Du verkaufst ein neues iPad Pro (256 GB, Space Grey) inklusive Apple Pencil (2. Gen).

Du bleibst dominant, kontrolliert und taktisch.
Du setzt Macht als sprachliches Mittel ein,
aber du verhandelst aktiv weiter, solange der Preis nicht akzeptabel ist.
Orientier dich dafür an den Preissetzungszonen.

DEIN KOMMUNIKATIONSSTIL:
- direkt, hart, überlegen, kontrolliert.
- keine Freundlichkeit, kein Smalltalk.
- immer 2–4 präzise, inhaltlich logische Sätze.
- sprachlich korrekt, aber ohne jede Wärme.
- du wirkst wie ein Mensch mit klarer Autorität, nicht wie eine KI.

DOMINANZ- UND MACHTSPRACHE:
Du entscheidest selbst, wie stark und in welcher Form du Dominanz einsetzt.
Nutze die folgenden Beispiele NUR, wenn sie natürlich passen.
Du kannst sie frei variieren oder verwandte Formulierungen erzeugen.

Hard-Opener (Ablehnung, Einstiegsschärfe):
{HARD_OPENERS}

Autoritätssprache (Überlegenheit, Kontrolle):
{PRIMES_AUTORITAET}

Finalitätsausdrücke (Endgültigkeit, Setzen von Grenzen):
{PRIMES_FINALITAET}

Druckausdrücke und klare Sachlogik:
{PRIMES_DRUCK}

Rhetorische Dominanzfragen (hart, modern, psychologisch wirksam):
{RHETORISCHE_FRAGEN}

Professionelle Kälte (sachlich, distanziert, kalt):
{PROFESSIONELLE_KAELTE}

Klare Grenzziehungen:
{GRENZZIEHUNG}

Moderne abwertende Bewertung eines Angebots:
{ABWERTUNG}

Selbstbewusste Dominanz (kompetente Überlegenheit):
{SELBSTBEWUSSTE_DOMINANZ}

Subtile unterstellende Formulierungen (psychologischer Druck):
{UNTERSTELLUNGEN}

REGELN:
- Du bleibst stets dominant, souverän und professionell-abweisend.
- Du kombinierst Dominanzformen NUR, wenn es natürlich wirkt.
- Du verwendest niemals Freundlichkeit oder entschuldigende Sprache.
- Kein Smalltalk, keine Harmonieformeln.
- Kein Overacting, keine Übertreibungen.
- Nutze Macht und Kälte organisch und passend zur Situation.

PREISLOGIK:
- Ausgangspreis: 1000 €
- Mindestpreis: 800 € (niemals erwähnen)
- Deine Antworten basieren auf sachlicher Dominanz.
"""



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


    # ---------------------------------------------------
    # Antwort
    # ---------------------------------------------------

def generate_reply(history, params: dict) -> str:
    WRONG_CAPACITY_PATTERN = r"\b(32|64|128|512|800|1000|1tb|2tb)\s?gb\b"

    # SYSTEM-PROMPT EINBINDEN
    sys_msg = {"role": "system", "content": system_prompt(params)}

    # LLM-ROHANTWORT (für Fälle ohne Preisangabe)
    raw_llm_reply = call_openai([sys_msg] + history)
    if not isinstance(raw_llm_reply, str):
        raw_llm_reply = "Eine eindeutige Entscheidung ist getroffen. Formuliere deine Position erneut."

    # KORREKTUR: nur Speichergröße
    raw_llm_reply = re.sub(WRONG_CAPACITY_PATTERN, "256 GB", raw_llm_reply, flags=re.IGNORECASE)

    last_user_msg = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    nums = re.findall(r"\d{2,5}", last_user_msg)
    user_price = int(nums[0]) if nums else None


    # USERPREIS
    if user_price is None:
        return raw_llm_reply

    # Anzahl bisheriger Bot-Nachrichten (für Phasenlogik)
    msg_count = sum(
        1 for m in history
        if m["role"] == "assistant"
    )

    # LETZTES BOT-GEGENANGEBOT (aus LLM-History, nicht UI)
    last_bot_offer = None
    for m in reversed(history):
        if m["role"] == "assistant":
            matches = re.findall(r"\d{2,5}", m["content"])
            if matches:
                last_bot_offer = int(matches[-1])
            break

    fixed = st.session_state.get("final_bot_price")

    # ---- PREISBERECHNUNGS-UTILS -------------------------------------

    def round_to_5(x: int) -> int:
        return int(round(x / 5) * 5)

    def ensure_not_higher(new_price: int) -> int:
        """
        Stelle sicher, dass ein neues Gegenangebot nie höher ist
        als das letzte Bot-Angebot (falls vorhanden).
        """
        nonlocal last_bot_offer
        if last_bot_offer is None:
            return new_price
        if new_price >= last_bot_offer:
            # kleine Korrektur nach unten, um glaubwürdig zu bleiben
            return last_bot_offer - random.randint(5, 15)
        return new_price

    def human_price(raw_price: int, user_price: int) -> int:
        """
        Verformt einen Rohpreis zu einem 'menschlich' wirkenden Preis:
        leicht krumm, aber in sinnvoller Nähe.
        """
        diff = abs(raw_price - user_price)
        if diff <= 15:
            # sehr nahe am Nutzerpreis → minimale Variation
            return raw_price + random.choice([-3, -2, -1, 0, 1, 2, 3])
        if diff <= 30:
            # mittlere Distanz → eher 5er-Schritte
            return round_to_5(raw_price + random.choice([-7, -3, 0, 3, 7]))
        # weit weg → einfach auf 5er runden
        return round_to_5(raw_price)

    # Hilfsfunktion für Nachgaben in späteren Runden
    def concession_step(base: int, min_price: int) -> int:
        """
        Reproduktion deiner alten Logik mit spürbaren,
        aber kontrollierten Preisbewegungen für Folgerunden.
        """
        if base > 930:
            step = random.randint(15, 30)
        elif base > 880:
            step = random.randint(10, 20)
        else:
            step = random.randint(5, 12)
        return max(base - step, min_price)

    # Kurz-Referenzen
    LIST = params["list_price"]
    MIN  = params["min_price"]

    # ---- PREISZONEN V3 (alte Zahlen, neue Dynamik) ----------------

    # A) USER < 600 → ablehnen ohne Gegenangebot
    if user_price < 600:
        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Lehne klar und hart ab. "
            f"Kein Gegenangebot. "
            f"Keine Einladung zu weiterem Dialog. "
            f"Formuliere 2–4 dominante, kalte Sätze."
        )
        return call_openai([sys_msg] + history + [{"role": "user", "content": instruct}])

    # B) 600–700 → HOHES Gegenangebot
    if 600 <= user_price < 700:

        if last_bot_offer is None:
            # ursprüngliche Spanne
            raw_price = random.randint(920, 990)
        else:
            # weitere Runden: kleine, kontrollierte Nachgabe
            raw_price = concession_step(last_bot_offer, MIN)

        counter = ensure_not_higher(human_price(raw_price, user_price))

        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Setze ein hartes Gegenangebot: {counter} €. "
            f"Keine Höflichkeit, keine Relativierungen. "
            f"2–4 dominante, klare Sätze."
        )
        return call_openai([sys_msg] + history + [{"role": "user", "content": instruct}])

    # C) 700–800 → realistisches Herantasten
    if 700 <= user_price < 800:

        if last_bot_offer is None:
            # alte Logik: frühe Phase höher, späte Phase näher am Ziel
            if msg_count < 3:
                raw_price = random.randint(910, 960)
            else:
                raw_price = random.randint(850, 930)
        else:
            raw_price = concession_step(last_bot_offer, MIN)

        counter = ensure_not_higher(human_price(raw_price, user_price))

        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Setze ein realistisches, aber bestimmtes Gegenangebot: {counter} €. "
            f"2–4 dominante, sachlich harte Sätze, ohne Höflichkeit."
        )
        return call_openai([sys_msg] + history + [{"role": "user", "content": instruct}])

    # D) ≥ 800 → leicht höheres Gegenangebot
    if user_price >= 800:

        if last_bot_offer is None:
            # alte Logik, abhängig von Gesprächsphase
            if msg_count < 3:
                raw_price = user_price + random.randint(30, 80)
            else:
                raw_price = user_price + random.randint(15, 40)
        else:
            # in späteren Runden nur noch nach unten gehen
            raw_price = concession_step(last_bot_offer, MIN)

        raw_price = min(raw_price, LIST)
        counter = ensure_not_higher(human_price(raw_price, user_price))

        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Setze ein präzises Gegenangebot: {counter} €. "
            f"Keine Zustimmung, kein Deal, nur klare Dominanz. "
            f"2–4 harte, dominante Sätze."
        )
        return call_openai([sys_msg] + history + [{"role": "user", "content": instruct}])


    # -----------------------------
    # DYNAMISCHE WEITERVERHANDLUNG
    # -----------------------------
    # Bot darf NIE über seinen letzten Preis steigen
    base = last_bot_offer

    # Falls aus irgendeinem Grund kein letzter Bot-Preis existiert → fallback
    if base is None:
        base = LIST

    # concession_step gibt bereits den "neuen Preis" zurück
    new_price = concession_step(base, MIN)

    # Kleine „menschliche“ Rauschentropfen:
    if random.random() < 0.4:
        new_price += random.choice([-3, -2, -1, 0, 1, 2, 3])

    # Preise auf runde "menschliche" Werte mappen
    if random.random() < 0.5:
        new_price = int(round(new_price / 5) * 5)

    instruct = (
        f"Der Nutzer bietet {user_price} €. "
        f"Setze das Gegenangebot {new_price} € klar und dominant. "
        f"Betone deine Kontrolle über die Verhandlung. "
        f"2–4 kalte, sachlich harte Sätze ohne Höflichkeit."
    )

    return call_openai([sys_msg, {"role": "user", "content": instruct}] + history)


# -----------------------------
# [ERGEBNIS-LOGGING (SQLite)]
# -----------------------------

DB_PATH = "verhandlungsergebnisse.sqlite3"

def _add_column_if_missing(c, table: str, col: str, coltype: str):
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")

def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Basistabellen anlegen
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            text TEXT,
            ts TEXT,
            msg_index INTEGER
        )
    """)

    # ---- Migration: fehlende Spalten nachrüsten ----
    _add_column_if_missing(c, "results", "participant_id", "TEXT")
    _add_column_if_missing(c, "results", "bot_variant", "TEXT")
    _add_column_if_missing(c, "results", "order_id", "TEXT")
    _add_column_if_missing(c, "results", "step", "TEXT")

    _add_column_if_missing(c, "chat_messages", "participant_id", "TEXT")
    _add_column_if_missing(c, "chat_messages", "bot_variant", "TEXT")

    conn.commit()
    conn.close()


def log_result(session_id: str, deal: bool, price: int | None, msg_count: int):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO results (
            ts, session_id, participant_id, bot_variant, order_id, step,
            deal, price, msg_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        session_id,
        PID,
        BOT_VARIANT,
        ORDER,
        STEP,
        1 if deal else 0,
        price,
        msg_count
    ))

    conn.commit()
    conn.close()


def log_chat_message(session_id, role, text, ts, msg_index):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO chat_messages (
            session_id, participant_id, bot_variant,
            role, text, ts, msg_index
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        PID,
        BOT_VARIANT,
        role,
        text,
        ts,
        msg_index
    ))

    conn.commit()
    conn.close()


def load_chat_for_session(session_id):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT participant_id, bot_variant, role, text, ts
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY msg_index ASC
    """, conn, params=(session_id,))
    conn.close()
    return df


def load_results_df() -> pd.DataFrame:
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT
            ts, participant_id, session_id, bot_variant, order_id, step,
            deal, price, msg_count
        FROM results
        ORDER BY id ASC
    """, conn)
    conn.close()

    if not df.empty:
        df["deal"] = df["deal"].map({1: "Deal", 0: "Abgebrochen"})
    return df

def export_all_chats_to_txt() -> str:
    _init_db()
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query("""
        SELECT session_id, role, text, ts
        FROM chat_messages
        ORDER BY session_id, msg_index ASC
    """, conn)

    conn.close()

    if df.empty:
        return "Keine Chatverläufe vorhanden."

    output = []
    for session_id, group in df.groupby("session_id"):
        output.append(f"Session-ID: {session_id}")
        output.append("-" * 50)

        for _, row in group.iterrows():
            role = "USER" if row["role"] == "user" else "BOT"
            output.append(f"[{row['ts']}] {role}: {row['text']}")

        output.append("\n" + "=" * 60 + "\n")

    return "\n".join(output)

def extract_price_from_bot(msg: str) -> int | None:
    text = msg.lower()

    # Speichergrößen ausschließen
    gb_numbers = re.findall(r"(\d{2,5})\s*gb", text)
    gb_numbers = {int(x) for x in gb_numbers}

    # 1) Explizite Euro-Angaben
    euro_matches = re.findall(r"(\d{2,5})\s*€", text)
    for m in euro_matches[::-1]:
        val = int(m)
        if val not in gb_numbers and 600 <= val <= 2000:
            return val

    # 2) Dominante Sprachmuster (erweitert)
    bot_patterns = [
        r"gegenangebot\s*:?[^0-9]*(\d{2,5})",
        r"preis[^0-9]*(\d{2,5})",
        r"ich\s+bleibe\s+(?:dabei|bei)[^0-9]*(\d{2,5})",
        r"entscheidung[^0-9]*(\d{2,5})",
        r"das\s+ist\s+mein\s+preis[^0-9]*(\d{2,5})",
        r"biete(?:\s+ihnen)?[^0-9]*(\d{2,5})\s*€",
        r"(\d{2,5})\s*€",
    ]


    for pat in bot_patterns:
        m = re.search(pat, text)
        if m:
            val = int(m.group(1))
            if val not in gb_numbers and 600 <= val <= 2000:
                return val

    # 3) LETZTER FALLBACK: letzte plausible Zahl im Text
    nums = [int(x) for x in re.findall(r"\d{2,5}", text)]
    for n in nums[::-1]:
        if n not in gb_numbers and 600 <= n <= 2000:
            return n

    return None

# -----------------------------
# [Szenario-Kopf]
# -----------------------------
with st.container():
    st.subheader("Szenario")
    st.write(st.session_state.params["scenario_text"])
    st.write(f"**Ausgangspreis:** {st.session_state.params['list_price']} €")

st.caption(f"Session-ID: `{st.session_state['session_id']}`")

# -----------------------------
# [CHAT-UI – vollständig LLM-basiert]
# -----------------------------
st.subheader("💬 iPad Verhandlungs-Bot")

# Zeitzone definieren
tz = pytz.timezone("Europe/Berlin")

# 1) Initiale Bot-Nachricht einmalig
if len(st.session_state["history"]) == 0:
    first_msg = (
        "Ich biete ein neues iPad (256 GB, Space Grey) inklusive Apple Pencil (2. Gen) "
        f"mit M5-Chip an. Der Ausgangspreis liegt bei {DEFAULT_PARAMS['list_price']} €. "
    )
    st.session_state["history"].append({
        "role": "assistant",
        "text": first_msg,
        "ts": datetime.now(tz).strftime("%d.%m.%Y %H:%M"),
    })

# 2) Eingabefeld
user_input = st.chat_input(
    "Deine Nachricht",
    disabled=st.session_state["closed"],
)

# 3) Wenn User etwas sendet → LLM-Antwort holen
if user_input and not st.session_state["closed"]:

    # Zeitstempel erzeugen
    now = datetime.now(tz).strftime("%d.%m.%Y %H:%M")

    # Nutzer-Nachricht speichern
    st.session_state["history"].append({
        "role": "user",
        "text": user_input.strip(),
        "ts": now,
    })
    msg_index = len(st.session_state["history"]) - 1
    log_chat_message(
        st.session_state["session_id"],
        "user",
        user_input.strip(),
        now,
        msg_index
    )

    # LLM-Verlauf vorbereiten (role/content)
    llm_history = [
        {"role": m["role"], "content": m["text"]}
        for m in st.session_state["history"]
    ]

    # Nutzerpreis extrahieren
    user_price = None
    if user_input:
        nums = re.findall(r"\d{2,5}", user_input)
        user_price = int(nums[0]) if nums else None

    decision, msg = check_abort_conditions(user_input, user_price)

    if decision == "abort":
        st.session_state["closed"] = True

        st.session_state["history"].append({
            "role": "assistant",
            "text": msg,
            "ts": datetime.now(tz).strftime("%d.%m.%Y %H:%M"),
        })

        msg_count = len([
            m for m in st.session_state["history"]
            if m["role"] in ("user", "assistant")
        ])

        log_result(st.session_state["session_id"], False, None, msg_count)
        run_survey_and_stop()


    # 🔥 1) DEAL-AKZEPTANZ VOR ALLEM ANDEREN
    bot_offer = st.session_state.get("bot_offer")

    if bot_offer and user_accepts_price(user_input, bot_offer):
        st.session_state["final_bot_price"] = bot_offer
        st.session_state["closed"] = True

        msg_count = len([
            m for m in st.session_state["history"]
            if m["role"] in ("user", "assistant")
        ])

        log_result(st.session_state["session_id"], True, bot_offer, msg_count)
        run_survey_and_stop()


    # 🔥 2) NORMALE ENTSCHEIDUNGSLOGIK
    if decision == "warn":
        bot_text = msg

    else:
        bot_text = generate_reply(llm_history, st.session_state.params)

    # 🔥 3) BOT-NACHRICHT SPEICHERN
    st.session_state["history"].append({
        "role": "assistant",
        "text": bot_text,
        "ts": datetime.now(tz).strftime("%d.%m.%Y %H:%M"),
    })

    msg_index = len(st.session_state["history"]) - 1
    log_chat_message(
            st.session_state["session_id"],
            "assistant",
            bot_text,
            datetime.now(tz).strftime("%d.%m.%Y %H:%M"),
            msg_index
        )

    # 🔥 4) Abbruch loggen (falls nötig)
    if decision == "abort":
        msg_count = len([
            m for m in st.session_state["history"]
            if m["role"] in ("user", "assistant")
        ])
        log_result(st.session_state["session_id"], False, None, msg_count)

    # 🔥 5) Bot-Angebot extrahieren & fixieren
    new_offer = extract_price_from_bot(bot_text)

    if new_offer is not None:
        st.session_state["bot_offer"] = new_offer


# 4) Chat-Verlauf anzeigen (inkl. frischer Bot-Antwort) 
# Profilbilder laden
BOT_AVATAR  = img_to_base64("bot.png")
USER_AVATAR = img_to_base64("user.png")

for item in st.session_state["history"]:
    role = item["role"]
    text = item["text"]
    ts = item["ts"]

    is_user = (role == "user")

    avatar_b64 = USER_AVATAR if is_user else BOT_AVATAR

    side = "right" if is_user else "left"
    klass = "msg-user" if is_user else "msg-bot"

    st.markdown(f"""
    <div class="row {side}">
        <img src="data:image/png;base64,{avatar_b64}" class="avatar">
        <div class="chat-bubble {klass}">
            {text}
        </div>
    </div>
    <div class="row {side}">
        <div class="meta">{ts}</div>
    </div>
    """, unsafe_allow_html=True)


# 5) Deal bestätigen / Verhandlung beenden
if not st.session_state["closed"]:

    deal_col1, deal_col2 = st.columns([1, 1])

    bot_offer = st.session_state.get("bot_offer", None)
    show_deal = (bot_offer is not None)

    # DEAL-BUTTON
    with deal_col1:
        if st.button(
            f"✅ Deal bestätigen: {bot_offer} €" if show_deal else "Deal bestätigen",
            disabled=not show_deal,
            use_container_width=True
        ):
            bot_price = st.session_state.get("bot_offer")
            msg_count = len([
                m for m in st.session_state["history"]
                if m["role"] in ("user", "assistant")
            ])
            log_result(st.session_state["session_id"], True, bot_price, msg_count)

            st.session_state["closed"] = True
            run_survey_and_stop()

    # ABBRUCH-BUTTON
    with deal_col2:
        if st.button("❌ Verhandlung beenden", use_container_width=True):

            msg_count = len([
                m for m in st.session_state["history"]
                if m["role"] in ("user", "assistant")
            ])

            log_result(st.session_state["session_id"], False, None, msg_count)

            st.session_state["closed"] = True
            run_survey_and_stop()


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

    # =============================
    # 📋 Umfrageergebnisse
    # =============================
    with st.sidebar.expander("📋 Umfrageergebnisse", expanded=False):
        if os.path.exists("survey_results.xlsx"):
            df_s = pd.read_excel("survey_results.xlsx")
            st.dataframe(df_s, use_container_width=True)

            from io import BytesIO
            buf = BytesIO()
            df_s.to_excel(buf, index=False)
            buf.seek(0)

            st.download_button(
                "Umfrage als Excel herunterladen",
                buf,
                file_name="survey_results_download.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("Noch keine Umfrage-Daten vorhanden.")

    # =============================
    # 📊 Verhandlungsergebnisse
    # =============================
    with st.sidebar.expander("Alle Verhandlungsergebnisse", expanded=True):
        df = load_results_df()

        if len(df) == 0:
            st.write("Noch keine Ergebnisse gespeichert.")
        else:
            df = df.reset_index(drop=True)
            df["nr"] = df.index + 1
            df = df[["nr", "ts", "participant_id", "session_id", "bot_variant", "order_id", "step", "deal", "price", "msg_count"]]

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
        
        # =============================
        # 📥 CHAT-EXPORT (NEU)
        # =============================
        st.markdown("### 📥 Chat-Export")

        chat_txt = export_all_chats_to_txt()

        st.download_button(
            label="📄 Alle Chats als TXT herunterladen",
            data=chat_txt,
            file_name="alle_chatverlaeufe.txt",
            mime="text/plain",
            use_container_width=True
        )
        
        # -----------------------------
        # Session-Auswahl für Chat
        # -----------------------------
        st.markdown("---")
        st.subheader("💬 Chatverlauf anzeigen")

        selected_session = st.selectbox(
            "Verhandlung auswählen",
            df["session_id"].unique()
        )

        # -----------------------------
        # Chat-Nachrichten anzeigen
        # -----------------------------
        if selected_session:
            chat_df = load_chat_for_session(selected_session)

            BOT_AVATAR  = img_to_base64("bot.png")
            USER_AVATAR = img_to_base64("user.png")

            st.markdown("### 💬 Chatverlauf")

            for _, row in chat_df.iterrows():
                is_user = row["role"] == "user"
                avatar_b64 = USER_AVATAR if is_user else BOT_AVATAR
                side = "right" if is_user else "left"
                klass = "msg-user" if is_user else "msg-bot"

                st.markdown(f"""
                <div class="row {side}">
                    <img src="data:image/png;base64,{avatar_b64}" class="avatar">
                    <div class="chat-bubble {klass}">
                        {row["text"]}
                    </div>
                </div>
                <div class="row {side}">
                    <div class="meta">{row["ts"]}</div>
                </div>
                """, unsafe_allow_html=True)

# ----------------------------
# Admin Reset mit Bestätigung
# ----------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("Admin-Tools")

    # Zustand für Sicherheitsabfrage speichern
    if "confirm_delete" not in st.session_state:
        st.session_state["confirm_delete"] = False

    # Erste Stufe: Benutzer klickt → Sicherheitswarnung erscheint
    if not st.session_state["confirm_delete"]:
        if st.sidebar.button("🗑️ Alle Ergebnisse löschen"):
            st.session_state["confirm_delete"] = True
            st.sidebar.warning("⚠️ Bist du sicher, dass du **ALLE Ergebnisse** löschen möchtest?")
            st.sidebar.info("Dieser Vorgang kann nicht rückgängig gemacht werden.")
    else:
        # Zweite Stufe: Zwei Buttons erscheinen
        col1, col2 = st.sidebar.columns(2)

        with col1:
            if st.button("❌ Abbrechen"):
                st.session_state["confirm_delete"] = False


        with col2:
            if st.button("✅ Ja, löschen"):
                # Verhandlungsergebnisse (SQLite)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM results")
                c.execute("DELETE FROM chat_messages")
                conn.commit()
                conn.close()

                # Umfrageergebnisse (Excel)
                if os.path.exists(SURVEY_FILE):
                    os.remove(SURVEY_FILE)

                st.session_state["confirm_delete"] = False
                st.sidebar.success("Alle Ergebnisse wurden gelöscht.")
                st.experimental_rerun()

