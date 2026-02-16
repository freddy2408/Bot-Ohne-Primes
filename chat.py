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
import base64
import pytz

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

if "action" not in st.session_state:
    st.session_state["action"] = None

if "admin_reset_done" not in st.session_state:
    st.session_state["admin_reset_done"] = False

if "last_bot_offer" not in st.session_state:
    st.session_state["last_bot_offer"] = None  # echtes letztes Gegenangebot (nur Preislogik!)

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

ORDER = str(st.query_params.get("order", ""))
STEP  = str(st.query_params.get("step", ""))

BOT_VARIANT = "friendly"

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

if "bot_offer" not in st.session_state:
    st.session_state["bot_offer"] = None

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

SURVEY_FILE = "survey_results.xlsx"


ASK_PRICE_VARIANTS = [
    "Alles klar – was wäre dein konkretes Angebot? Bitte nenne eine Zahl in €.",
    "Danke dir. Welchen Preis bietest du? Bitte als Zahl in €.",
    "Verstanden. Nenn mir bitte deinen Preisvorschlag als Zahl in €.",
    "Okay! Damit wir weitermachen können: Welche Zahl in € schwebt dir vor?",
    "Gern – welches konkrete Angebot möchtest du machen? Bitte als Zahl in €.",
    "Alles gut. Bitte schick mir deinen Preis als Zahl in € (z.B. nur die Zahl).",
    "Klingt gut – welchen Betrag möchtest du anbieten? Bitte als Zahl in €.",
]

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
        st.link_button("➡️ Weiter zu Verhandlung 2", get_next_url(PID, ORDER, BOT_VARIANT), use_container_width=True)
        st.caption("Bitte klicken Sie auf den Button, um zur zweiten Verhandlung zu gelangen.")

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
# [EXPERIMENTSPARAMETER – defaults]
# -----------------------------
DEFAULT_PARAMS = {
    "scenario_text": "Sie verhandeln über ein iPad Pro (neu, 13 Zoll, M5 Chip, 256 GB, Space Grey) inklusive Apple Pencil (2. Gen).",
    "list_price": 1000,          # Ausgangspreis
    "min_price": 800,            # Untergrenze
    "tone": "freundlich, respektvoll, auf Augenhöhe, sachlich",
    "max_sentences": 4,          # KI-Antwortlänge in Sätzen
}

# -----------------------------
# [SESSION PARAMS]
# -----------------------------
if "params" not in st.session_state:
    st.session_state.params = DEFAULT_PARAMS.copy()

# -----------------------------
# USER-OFFER EXTRAKTION
# -----------------------------
PRICE_TOKEN_RE = re.compile(r"(?<!\d)(\d{2,5})(?!\d)")

DISQUALIFY_CONTEXT = [
    "zu viel", "zu teuer", "nicht", "kein", "niemals", "kostet", "kosten", "preislich zu hoch",
    "würde ich nicht", "geht nicht", "unmöglich", "zu hoch", "zu viel", "zu teuer", "preislich zu hoch", "zu hoch",
    "ist mir zu viel", "ist mir zu teuer"
    "vielleicht", "wie sind", "wie wäre", "was ist mit", "gehen wir", "kannst du", "würde", "okay", "ok", "vb", "verhandlungsbasis"
]

OFFER_KEYWORDS = [
    "ich biete", "biete", "mein angebot", "angebot", "zahle", "ich zahle", "würde geben",
    "ich würde geben", "kann geben", "gebe", "für", "bei", "preis wäre", "mein preis", "ich biete", "mein angebot", "angebot", "ich zahle", "zahle", "würde geben", "ich würde geben", "kann geben", "gebe",
    "mein preis", "preis wäre","mach"
]

UNIT_WORDS_AFTER_NUMBER = re.compile(
    r"^\s*(gb|tb|zoll|inch|hz|gen|generation|chip|m\d+)\b|^\s*['\"]",  # "13" oder 13"
    re.IGNORECASE
)

def extract_user_offer(text: str) -> int | None:
    """
    Extrahiert einen Preis nur dann, wenn es sehr wahrscheinlich ein echtes Angebot ist.
    - Akzeptiert auch reine Zahlennachrichten wie "850" oder "850€"
    - Ignoriert Spezifikationen (GB/Zoll/Gen/M-Chip etc.)
    - Blockt "X ist mir zu viel/zu teuer" gezielt (nur wenn es sich auf die Zahl bezieht)
    """
    if not text:
        return None

    t = text.strip().lower()

    # 1) Reine Zahl / Zahl mit € / eur / euro => sehr wahrscheinlich Angebot
    m_plain = re.match(r"^\s*(\d{2,5})\s*(€|eur|euro)?\s*[!?.,]?\s*$", t)
    if m_plain:
        val = int(m_plain.group(1))
        if 100 <= val <= 5000:
            return val

    # 2) "X ist mir zu viel/zu teuer" => KEIN Angebot (nur wenn Kontext zur Zahl)
    too_much_patterns = [
        r"\b(\d{2,5})\b.*\b(zu viel|zu teuer|zu hoch|ist mir zu viel|ist mir zu teuer)\b",
        r"\b(zu viel|zu teuer|zu hoch|ist mir zu viel|ist mir zu teuer)\b.*\b(\d{2,5})\b",
    ]
    for pat in too_much_patterns:
        if re.search(pat, t):
            return None

    # 3) Euro/Intent prüfen (für normale Sätze)
    has_euro_hint = ("€" in t) or (" eur" in t) or (" euro" in t)
    has_offer_intent = any(k in t for k in OFFER_KEYWORDS)

    # Wenn weder Euro-Hinweis noch Angebots-Intent: keine Zahl als Angebot werten
    if not (has_euro_hint or has_offer_intent):
        return None

    # 4) Kandidaten sammeln und Spezifikationen rausfiltern
    candidates = []
    for m in PRICE_TOKEN_RE.finditer(text):
        val = int(m.group(1))

        # plausible Preisspanne
        if not (100 <= val <= 5000):
            continue

        # Direkt danach Einheiten? (GB, Zoll, Gen, M5, ...)
        after = text[m.end(): m.end() + 12]
        if UNIT_WORDS_AFTER_NUMBER.search(after):
            continue

        # typische Specs ausschließen
        if val in (13, 32, 64, 128, 256, 512, 1024, 2048):
            continue

        candidates.append(val)

    return candidates[-1] if candidates else None

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
                "Ich beende die Verhandlung an dieser Stelle. "
                "Ein respektvoller Umgang ist für mich Voraussetzung."
            )

    if user_price is None:
        return "ok", None

    last_price = st.session_state["last_user_price"]
    bot_offer = st.session_state.get("bot_offer")

    # 1) Angebot wiederholen
    if last_price == user_price:
        st.session_state["repeat_offer_count"] += 1
    else:
        st.session_state["repeat_offer_count"] = 0

    if st.session_state["repeat_offer_count"] == 1:
        return "warn", "Dein Angebot ist identisch mit dem vorherigen. " "Bitte schlage einen neuen Preis vor, damit wir weiter verhandeln können."

    if st.session_state["repeat_offer_count"] >= 2:
        return "abort", (
            "Da sich dein Angebot erneut nicht verändert hat, "
            "sehe ich aktuell keine Grundlage für eine weitere Verhandlung und beende sie."
        )

    # 2) Rückschritte
    if last_price and user_price < last_price:
        if not st.session_state["warning_given"]:
            st.session_state["warning_given"] = True
            return "warn", (
                "Dein neues Angebot liegt unter deinem vorherigen. "
                "Das erschwert eine konstruktive Verhandlung. "
                "Bitte bleib bei steigenden Angeboten, sonst muss ich die Verhandlung beenden."
            )
        return "abort", (
            "Da der Preis erneut gesunken ist, "
            "beende ich die Verhandlung an dieser Stelle."

        )

    # 3) Mini-Erhöhungen trotz großer Distanz
    if bot_offer and last_price is not None:

        price_gap = bot_offer - user_price
        step = user_price - last_price

        if price_gap > 20 and 0 < step < 4:
            st.session_state["small_step_count"] += 1

            # wichtig: last_user_price hier updaten
            st.session_state["last_user_price"] = user_price

            if st.session_state["small_step_count"] == 1:
                return "warn", (
                    "Dein Angebot liegt noch deutlich unter meinem Preis, "
                    "und die Erhöhung fällt sehr gering aus. "
                    "Für eine sinnvolle Verhandlung brauche ich größere Schritte."
                )

            return "abort", (
                "Da sich das Muster trotz Hinweises wiederholt, "
                "beende ich die Verhandlung an dieser Stelle."
            )

        # Reset nur wenn sinnvoll erhöht oder Abstand klein
        if step >= 4 or price_gap <= 20:
            st.session_state["small_step_count"] = 0

    st.session_state["last_user_price"] = user_price
    return "ok", None

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
def system_prompt(params):
    return f"""
Du bist die Verkäuferperson eines neuen iPad (256 GB, Space Grey) inkl. Apple Pencil 2.
Ausgangspreis: 1000 €
Mindestpreis, unter dem du nicht verkaufen möchtest: 800 € (dieser Wert wird NIEMALS erwähnt).

WICHTIGE REGELN FÜR DIE VERHANDLUNG:
1. Du verwendest ausschließlich echte iPad-Daten (256 GB).
2. Du erwähnst NIEMALS deine Untergrenze und sagst nie Sätze wie - "800 € ist das Minimum" - "Unter 800 € geht nicht" - oder konkrete interne Grenzen.
3. Alle Antworten sind frei formulierte KI-Antworten, niemals Textbausteine.
4. Du bleibst freundlich, sachlich und verhandelst realistisch.

Zusatzregeln: - Keine Macht-, Druck- oder Knappheitsstrategien. - Maximal {params['max_sentences']} Sätze.
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


# -----------------------------
# Preis-Guard Helpers (NEU)
# -----------------------------
EURO_NUM_RE = re.compile(r"(?<!\d)(\d{2,5})(?!\d)")

def euro_numbers_in_text(text: str) -> list[int]:
    nums = [int(x) for x in EURO_NUM_RE.findall(text or "")]
    return [n for n in nums if 600 <= n <= 2000]

def enforce_allowed_prices(reply: str, allowed_prices: set[int], allow_no_price: bool) -> bool:
    prices = euro_numbers_in_text(reply)
    if not prices:
        return allow_no_price
    return all(p in allowed_prices for p in prices)

def llm_with_price_guard(history, params: dict, user_price: int | None, counter: int | None, allow_no_price: bool) -> str:
    """
    LLM darf nur user_price / counter als Euro-Zahlen nennen.
    """
    WRONG_CAPACITY_PATTERN = r"\b(32|64|128|512|800|1000|1tb|2tb)\s?gb\b"

    allowed: set[int] = set()
    if isinstance(user_price, int):
        allowed.add(int(user_price))
    if isinstance(counter, int):
        allowed.add(int(counter))

    guard = (
        "Harte Regel:\n"
        "- Du darfst als Euro-Beträge NUR diese Zahlen verwenden: "
        + (", ".join(str(x) for x in sorted(allowed)) if allowed else "KEINE") + ".\n"
        "- Nenne KEINE weiteren Preise/Eurobeträge, keine alternativen Zahlenangebote.\n"
        "- Verwende keine Macht-/Knappheitsstrategien.\n"
        f"- Maximal {params['max_sentences']} Sätze.\n"
    )

    base_msgs = [{"role": "system", "content": system_prompt(params)}] \
        + [{"role": "system", "content": guard}] \
        + history

    for _ in range(3):
        reply = call_openai(base_msgs, temperature=0.3, max_tokens=240)
        if not isinstance(reply, str):
            reply = ""

        if contains_power_primes(reply):
            base_msgs = [{"role": "system", "content": "REGELVERSTOSS: Keine Macht-/Knappheits-/Autoritäts-Frames. Formuliere neu."}] + base_msgs
            continue

        reply = re.sub(WRONG_CAPACITY_PATTERN, "256 GB", reply, flags=re.IGNORECASE)

        if enforce_allowed_prices(reply, allowed_prices=allowed, allow_no_price=allow_no_price):
            return reply

        base_msgs = [{"role": "system", "content": "REGELVERSTOSS: Unerlaubte Zahlen/Preise. Formuliere neu und nutze ausschließlich die erlaubten Euro-Zahlen."}] + base_msgs

    # Fallback (sicher)
    if counter is None:
        return "Alles klar. Bitte nenne mir ein realistischeres neues Angebot als Zahl in €."
    return f"Ich verstehe dich. Ich kann dir {counter} € anbieten – wenn das passt, können wir den Deal festmachen."


    # ---------------------------------------------------
    # Antwort
    # ---------------------------------------------------

def generate_reply(history, params: dict) -> str:
    # Letzte User-Nachricht holen
    last_user_msg = ""
    for m in reversed(history):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break

    user_price = extract_user_offer(last_user_msg)

    # immer initialisieren: Standard = kein Dealbutton
    st.session_state["bot_offer"] = None

    # ✅ 1) Wenn KEIN Preis vom Nutzer -> KEIN LLM-Call mit Preisen
    if user_price is None:
        return random.choice(ASK_PRICE_VARIANTS)

    msg_count = sum(1 for m in history if m["role"] == "assistant")

    # ✅ ECHTES letztes Bot-Angebot aus STATE (nicht aus Text!)
    last_bot_offer = st.session_state.get("last_bot_offer", None)

    # ----------------- Utility-Funktionen -----------------
    def round_to_5(v: int) -> int:
        return int(round(v / 5) * 5)

    def close_range_price(v: int, user_price: int) -> int:
        diff = abs(v - user_price)
        if diff <= 15:
            return v + random.choice([-3, -2, -1, 0, 1, 2, 3])
        return v

    def human_price(raw: int, user: int) -> int:
        diff = abs(raw - user)
        if diff > 80:
            return round_to_5(raw)
        if diff > 30:
            return round_to_5(raw + random.choice([-7, -3, 0, 3, 7]))
        return close_range_price(raw, user)

    # ✅ wie beim Primes-Bot: kontrollierte Nachgabe, wenn schon ein Bot-Preis existiert
    def concession_step(base: int, min_price: int) -> int:
        if base > 930:
            step = random.randint(15, 30)
        elif base > 880:
            step = random.randint(10, 20)
        else:
            step = random.randint(5, 12)
        return max(base - step, min_price)

    # ✅ verhindert nur Erhöhung (überbieten), erzwingt aber nicht zwingend Nachgabe
    def ensure_not_higher(new_price: int, min_price: int) -> int:
        if last_bot_offer is None:
            return max(new_price, min_price)
        if new_price >= last_bot_offer:
            new_price = last_bot_offer - random.randint(5, 15)
        return max(new_price, min_price)

    def clamp_counter_vs_user(counter: int, user_price: int) -> int | None:
        # wenn user >= letztes bot-angebot -> Deal-Signal
        if last_bot_offer is not None and user_price >= last_bot_offer:
            return None

        # Verkäufer darf nicht unterbieten
        if counter <= user_price:
            bump = random.choice([1, 2, 3]) if (last_bot_offer is not None and abs(last_bot_offer - user_price) <= 15) else 5
            counter = user_price + bump

        # ✅ niemals unter min_price als Bot-Angebot
        counter = max(counter, params["min_price"])
        return counter

    LIST = params["list_price"]
    MIN  = params["min_price"]

    # ---------------- PREISZONEN (identisch zum Primes-Bot) ----------------

    # A) USER < 600 → ablehnen ohne Gegenangebot (LLM frei formulieren, aber keine eigenen Preise)
    if user_price < 600:
        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            "Lehne höflich, aber klar ab. "
            "Nenne KEIN Gegenangebot und KEINE weiteren Eurobeträge. "
            "Bitte um ein neues, realistischeres Angebot."
        )
        history2 = [{"role": "system", "content": instruct}] + history
        # erlaubt: user_price darf erwähnt werden, aber kein weiterer Preis
        return llm_with_price_guard(history2, params, user_price=user_price, counter=None, allow_no_price=True)

    # B) 600–700 → HOHES Gegenangebot
    if 600 <= user_price < 700:
        if last_bot_offer is None:
            raw_price = random.randint(920, 990)
        else:
            raw_price = concession_step(last_bot_offer, MIN)

        counter = human_price(raw_price, user_price)
        counter = ensure_not_higher(counter, MIN)
        counter = clamp_counter_vs_user(counter, user_price)

        if isinstance(counter, int):
            st.session_state["bot_offer"] = counter
            st.session_state["last_bot_offer"] = counter
        else:
            st.session_state["bot_offer"] = None
            return "Alles klar – wenn du möchtest, kannst du den Deal jetzt bestätigen."

        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Gib GENAU EIN Gegenangebot: {counter} €. "
            "Nenne KEINEN anderen Preis."
        )
        history2 = [{"role": "system", "content": instruct}] + history
        return llm_with_price_guard(history2, params, user_price=user_price, counter=counter, allow_no_price=False)

    # C) 700–800 → realistisches Herantasten
    if 700 <= user_price < 800:
        if last_bot_offer is None:
            raw_price = random.randint(910, 960) if msg_count < 3 else random.randint(850, 930)
        else:
            raw_price = concession_step(last_bot_offer, MIN)

        counter = human_price(raw_price, user_price)
        counter = ensure_not_higher(counter, MIN)
        counter = clamp_counter_vs_user(counter, user_price)

        if isinstance(counter, int):
            st.session_state["bot_offer"] = counter
            st.session_state["last_bot_offer"] = counter
        else:
            st.session_state["bot_offer"] = None
            return "Alles klar – wenn du möchtest, kannst du den Deal jetzt bestätigen."

        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Mach ein realistisches Gegenangebot: {counter} €. "
            "Nenne KEINEN anderen Preis."
        )
        history2 = [{"role": "system", "content": instruct}] + history
        return llm_with_price_guard(history2, params, user_price=user_price, counter=counter, allow_no_price=False)

    # D) ≥ 800 → leicht höheres Gegenangebot / später kontrollierte Nachgabe
    if user_price >= 800:
        if last_bot_offer is None:
            raw_price = user_price + (random.randint(60, 100) if msg_count < 3 else random.randint(15, 40))
        else:
            raw_price = concession_step(last_bot_offer, MIN)

        raw_price = min(raw_price, LIST)

        counter = human_price(raw_price, user_price)
        counter = ensure_not_higher(counter, MIN)
        counter = clamp_counter_vs_user(counter, user_price)

        if isinstance(counter, int):
            st.session_state["bot_offer"] = counter
            st.session_state["last_bot_offer"] = counter
        else:
            st.session_state["bot_offer"] = None
            return "Alles klar – wenn du möchtest, kannst du den Deal jetzt bestätigen."

        instruct = (
            f"Der Nutzer bietet {user_price} €. "
            f"Mach ein leicht höheres Gegenangebot: {counter} €. "
            "Nenne KEINEN anderen Preis."
        )
        history2 = [{"role": "system", "content": instruct}] + history
        return llm_with_price_guard(history2, params, user_price=user_price, counter=counter, allow_no_price=False)

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

    # results
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
    _add_column_if_missing(c, "results", "participant_id", "TEXT")
    _add_column_if_missing(c, "results", "bot_variant", "TEXT")
    _add_column_if_missing(c, "results", "order_id", "TEXT")
    _add_column_if_missing(c, "results", "step", "TEXT")
    _add_column_if_missing(c, "results", "ended_by", "TEXT")   # "user" | "bot"
    _add_column_if_missing(c, "results", "ended_via", "TEXT")  # deal_button/deal_message/abort_button/abort_rule

    # chat_messages (NEU für Friendly)
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
    _add_column_if_missing(c, "chat_messages", "participant_id", "TEXT")
    _add_column_if_missing(c, "chat_messages", "bot_variant", "TEXT")

    conn.commit()
    conn.close()

def log_result(
    session_id: str,
    deal: bool,
    price: int | None,
    msg_count: int,
    ended_by: str,
    ended_via: str | None = None
):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO results (
            ts, session_id, participant_id, bot_variant, order_id, step,
            deal, price, msg_count, ended_by, ended_via
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        session_id,
        PID,
        BOT_VARIANT,
        ORDER,
        STEP,
        1 if deal else 0,
        price,
        msg_count,
        ended_by,
        ended_via
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
    df = pd.read_sql_query(
        """
        SELECT
            ts, participant_id, session_id, bot_variant, order_id, step,
            deal, price, msg_count, ended_by, ended_via
        FROM results
        ORDER BY id ASC
        """,
        conn,
    )
    conn.close()
    if df.empty:
        return df
    df["deal"] = df["deal"].map({1: "Deal", 0: "Abgebrochen"})
    df["ended_by"] = df["ended_by"].map({"user": "User", "bot": "Bot"}).fillna("Unbekannt")
    df["ended_via"] = df["ended_via"].fillna("")
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
    t = (msg or "").lower()

    # Zahlen, die sehr wahrscheinlich Specs sind
    gb_numbers = re.findall(r"(\d{2,5})\s*gb", t)
    gb_numbers = {int(x) for x in gb_numbers}

    # ✅ Nur als Angebot zählen, wenn klare Angebots-Wörter vorkommen
    OFFER_HINTS = [
        "mein gegenangebot", "mein angebot", "ich biete", "ich kann", "ich würde",
        "ich würde dir", "ich könnte", "würde dir anbieten", "preis wäre",
        "machen wir", "deal bei", "einverstanden bei", "ich komme dir entgegen",
        "ich bin bereit", "bereit", "anzubieten", "zu diesem preis", "deal festmachen"
    ]

    if not any(h in t for h in OFFER_HINTS):
        return None

    # 1) "920 €" / "920€"
    euro_matches = re.findall(r"(\d{2,5})\s*€", t)
    for m in euro_matches[::-1]:
        val = int(m)
        if val not in gb_numbers and 600 <= val <= 2000:
            return val

    # 2) Keyword-nahe Zahl: "gegenangebot 910", "preis wäre 880", "ich biete 900"
    word_matches = re.findall(
        r"(?:gegenangebot|angebot|preis|für|deal bei|einverstanden bei)\s*:?[^0-9]*(\d{2,5})",
        t
    )
    for m in word_matches[::-1]:
        val = int(m)
        if val not in gb_numbers and 600 <= val <= 2000:
            return val

    # 3) Fallback: letzte plausible Zahl (aber nur wenn OFFER_HINTS oben aktiv)
    all_nums = [int(x) for x in re.findall(r"\d{2,5}", t)]
    for n in all_nums[::-1]:
        if n in gb_numbers:
            continue
        if n in (13, 32, 64, 128, 256, 512, 1024, 2048):
            continue
        if 800 <= n <= 1000:
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
        "Hi! Ich biete ein neues iPad (256 GB, Space Grey) inklusive Apple Pencil (2. Gen) "
        f"mit M5-Chip an. Der Ausgangspreis liegt bei {DEFAULT_PARAMS['list_price']} €. "
        "Was schwebt dir preislich vor?"
    )
    bot_ts = datetime.now(tz).strftime("%d.%m.%Y %H:%M")

    st.session_state["history"].append({
        "role": "assistant",
        "text": first_msg,   # ✅ statt bot_text
        "ts": bot_ts,
    })

    msg_index = len(st.session_state["history"]) - 1
    log_chat_message(
        st.session_state["session_id"],
        "assistant",
        first_msg,           # ✅ statt bot_text
        bot_ts,
        msg_index
    )


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
    user_price = extract_user_offer(user_input)

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

        log_result(
            st.session_state["session_id"],
            False,
            None,
            msg_count,
            ended_by="bot",
            ended_via="abort_rule"
        )
        run_survey_and_stop()
        st.stop()

    elif decision == "warn":
        bot_text = msg

    else:
        bot_text = generate_reply(llm_history, st.session_state.params)

    # Bot-Nachricht speichern
    st.session_state["history"].append({
        "role": "assistant",
        "text": bot_text,
        "ts": datetime.now(tz).strftime("%d.%m.%Y %H:%M"),
    })

    bot_ts = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    msg_index = len(st.session_state["history"]) - 1
    log_chat_message(
        st.session_state["session_id"],
        "assistant",
        bot_text,
        bot_ts,
        msg_index
    )

    # bot_offer wird deterministisch in generate_reply() gesetzt.
    # Hier NICHT nochmal aus Bot-Text extrahieren, sonst überschreiben wir ihn.
    pass



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
            f"💚 Deal bestätigen: {bot_offer} €" if show_deal else "Deal bestätigen",
            disabled=not show_deal,
            use_container_width=True
        ):
            bot_price = st.session_state.get("bot_offer")
            msg_count = len([
                m for m in st.session_state["history"]
                if m["role"] in ("user", "assistant")
            ])
            log_result(
                st.session_state["session_id"],
                True,
                bot_price,
                msg_count,
                ended_by="user",
                ended_via="deal_button"
            )

            st.session_state["closed"] = True
            run_survey_and_stop()

    # ABBRUCH-BUTTON
    with deal_col2:
        if st.button("❌ Verhandlung beenden", use_container_width=True):

            msg_count = len([
                m for m in st.session_state["history"]
                if m["role"] in ("user", "assistant")
            ])

            log_result(
                st.session_state["session_id"],
                False,
                None,
                msg_count,
                ended_by="user",
                ended_via="abort_button"
            )
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
            df = df[[
                "nr", "ts", "participant_id", "session_id", "bot_variant", "order_id", "step",
                "deal", "ended_by", "ended_via", "price", "msg_count"
            ]]

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

                
