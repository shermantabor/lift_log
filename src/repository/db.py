"""
Database access layer for Lift Log.

Handles PostgreSQL database initialization, connections, and CRUD
operations for storing and retrieving lift data.
"""

import os
from typing import Optional, Sequence
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get('DATABASE_URL')

SetRow = tuple[float, int, int]  # (weight, reps, is_1rm)

def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def db_init_db():
    '''initialize database, create tables if they don't exist'''
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                performed_at TEXT NOT NULL,
                notes TEXT,
                ended_at TEXT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        ''')

        cur.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_session_per_user
            ON sessions (user_id)
            WHERE ended_at IS NULL;
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS sets (
                set_id SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL,
                exercise TEXT NOT NULL,
                weight REAL NOT NULL CHECK(weight >= 0),
                reps INTEGER NOT NULL CHECK(reps > 0),
                set_index INTEGER NOT NULL CHECK(set_index > 0),
                is_1rm INTEGER NOT NULL CHECK(is_1rm IN (0, 1)),
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        ''')

        cur.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sets_unique_order
            ON sets(session_id, exercise, set_index);
        ''')

        conn.commit()

def db_create_session(conn, user_id, performed_at, notes) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (user_id, performed_at, ended_at, notes) VALUES (%s, %s, %s, %s) RETURNING session_id;",
        (user_id, performed_at, None, notes)
    )
    session_id = cur.fetchone()[0]
    return session_id

def db_end_all_open_sessions(conn, user_id: int, performed_at: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sessions
        SET ended_at = %s
        WHERE user_id = %s
        AND ended_at IS NULL
        """,
        (performed_at, user_id)
    )
    return cur.rowcount

def db_get_next_set_index(conn, session_id: int, exercise: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(set_index), 0) FROM sets WHERE session_id = %s AND exercise = %s",
        (session_id, exercise)
    )
    return cur.fetchone()[0] + 1

def db_insert_sets(conn, session_id, exercise, rows: Sequence[SetRow]) -> int:
    start_index = db_get_next_set_index(conn, session_id, exercise)
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO sets (session_id, exercise, weight, reps, is_1rm, set_index)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            (session_id, exercise, weight, reps, is_1rm, start_index + i)
            for i, (weight, reps, is_1rm) in enumerate(rows)
        ],
    )
    return cur.rowcount

def db_get_active_session(conn, user_id: int) -> Optional[int]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session_id FROM sessions
        WHERE user_id = %s AND ended_at IS NULL
        ORDER BY session_id DESC
        LIMIT 1
        """,
        (user_id,)
    )
    row = cur.fetchone()
    return row[0] if row else None

def db_get_user(conn, username: str) -> Optional[tuple]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id, password_hash FROM users WHERE username = %s;", (username,))
    return cur.fetchone()

def db_create_user(conn, created_at: str, username: str, password_hash: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s) RETURNING user_id;",
        (username, password_hash, created_at)
    )
    return cur.fetchone()[0]

def db_get_sets_by_session(conn, session_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT set_id, exercise, weight, reps, is_1rm
        FROM sets WHERE session_id = %s
        ORDER BY set_id DESC
        """,
        (session_id,)
    )
    return cur.fetchall()

def db_get_active_session_row(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT session_id, user_id, performed_at, notes, ended_at
        FROM sessions
        WHERE user_id = %s AND ended_at IS NULL
        LIMIT 1;
    """, (user_id,))
    return cur.fetchone()

def db_get_sessions_for_user(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT session_id, user_id, performed_at, notes, ended_at
        FROM sessions
        WHERE user_id = %s
        ORDER BY performed_at DESC;
    """, (user_id,))
    return cur.fetchall()

def db_get_sets_for_session(conn, session_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT exercise, set_id, weight, reps, set_index, is_1rm
        FROM sets WHERE session_id = %s
        ORDER BY exercise, set_index;
    """, (session_id,))
    return cur.fetchall()

def db_get_exercises_for_user(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT sets.exercise
        FROM sets
        JOIN sessions ON sets.session_id = sessions.session_id
        WHERE sessions.user_id = %s
        ORDER BY sets.exercise;
    """, (user_id,))
    return cur.fetchall()

def db_get_sets_for_exercise(conn, user_id: int, exercise: str):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT sets.set_id, sets.weight, sets.reps, sets.is_1rm, sessions.performed_at
        FROM sets
        JOIN sessions ON sets.session_id = sessions.session_id
        WHERE sessions.user_id = %s AND sets.exercise = %s
        ORDER BY sessions.performed_at ASC;
    """, (user_id, exercise))
    return cur.fetchall()