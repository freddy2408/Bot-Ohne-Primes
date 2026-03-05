import streamlit as st
import pandas as pd
from db_common import get_conn, init_db

st.set_page_config(page_title="Scoreboard", page_icon="🏆")

pid = st.query_params.get("pid", "")
if not pid:
    st.error("Keine Teilnehmer-ID (pid) in der URL.")
    st.stop()

init_db()
conn = get_conn()
cur = conn.cursor()

# Gate: beide Surveys müssen existieren
cur.execute("""
    SELECT COUNT(DISTINCT step)
    FROM survey
    WHERE participant_id = %s AND step IN ('1','2')
""", (pid,))
n = cur.fetchone()[0] or 0

if n < 2:
    conn.close()
    st.warning("Bitte erst beide Verhandlungen inkl. Fragebogen abschließen.")
    st.stop()

# Scoreboard-Daten: nur Teilnehmer, die beide Steps im results haben
df = pd.read_sql_query("""
    SELECT participant_id, step, deal, price, msg_count
    FROM results
""", conn)
conn.close()

# Beispiel-Punkte: Rabatt (1000 - Preis), Abbruch = 0
LIST_PRICE = 1000
df["points"] = df.apply(lambda r: (LIST_PRICE - r["price"]) if r["deal"] == 1 and pd.notna(r["price"]) else 0, axis=1)

# Nur vollständige Teilnehmer (beide Steps)
complete = df.groupby("participant_id")["step"].nunique()
complete_pids = complete[complete >= 2].index
df = df[df["participant_id"].isin(complete_pids)]

score = (df.groupby("participant_id")
           .agg(total_points=("points","sum"),
                total_msgs=("msg_count","sum"))
           .reset_index())

score = score.sort_values(["total_points","total_msgs"], ascending=[False, True]).reset_index(drop=True)
score["rank"] = score.index + 1
score["pid_short"] = score["participant_id"].astype(str).str[-4:]

st.title("🏆 Scoreboard")
st.dataframe(score[["rank","pid_short","total_points","total_msgs"]], use_container_width=True, hide_index=True)

me = score[score["participant_id"] == pid]
if not me.empty:
    st.success(f"Dein Rang: #{int(me['rank'].iloc[0])}")
