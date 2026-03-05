# db_common.py
import streamlit as st
import psycopg2

def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # 1) Assignment (Reihenfolge AB/BA)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            pid TEXT PRIMARY KEY,
            order_code TEXT NOT NULL,
            created_ts TEXT NOT NULL
        )
    """)

    # 2) Verhandlungsergebnisse
    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id BIGSERIAL PRIMARY KEY,
            ts TEXT,
            session_id TEXT,
            participant_id TEXT,
            bot_variant TEXT,
            order_id TEXT,
            step TEXT,
            deal INTEGER,
            price INTEGER,
            msg_count INTEGER,
            ended_by TEXT,
            ended_via TEXT
        )
    """)

    # 3) Chatverläufe (optional fürs Admin-Dashboard)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id BIGSERIAL PRIMARY KEY,
            session_id TEXT,
            participant_id TEXT,
            bot_variant TEXT,
            role TEXT,
            text TEXT,
            ts TEXT,
            msg_index INTEGER
        )
    """)

    # 4) Surveys (wichtig fürs “Gate” und fürs Scoreboard)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS survey (
            id BIGSERIAL PRIMARY KEY,
            survey_ts_utc TEXT,
            participant_id TEXT,
            session_id TEXT,
            bot_variant TEXT,
            order_id TEXT,
            step TEXT,

            age TEXT,
            gender TEXT,
            education TEXT,
            field TEXT,
            field_other TEXT,

            satisfaction_outcome INTEGER,
            satisfaction_process INTEGER,
            fairness INTEGER,
            better_result INTEGER,
            deviation INTEGER,
            willingness INTEGER,
            again TEXT
        )
    """)

    conn.commit()
    conn.close()
