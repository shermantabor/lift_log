"""
Database access layer for Lift Log.

Handles PostgreSQL database initialization, connections, and CRUD
operations for storing and retrieving lift data.
"""

import os
from contextlib import contextmanager
from typing import Optional, Sequence
import psycopg2
import psycopg2.extras

SetRow = tuple[float, int, int]  # (weight, reps, is_1rm)

def _database_url() -> str:
    '''
    Read at call time, not import time, so tests can point the app at a scratch
    database without depending on import order.
    '''
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return url

@contextmanager
def get_conn():
    '''
    Commits on clean exit and rolls back on exception (psycopg2's own `with conn`
    semantics), then always closes. Closing explicitly keeps connection release
    deterministic instead of leaving it to garbage collection.
    '''
    conn = psycopg2.connect(_database_url())
    try:
        with conn:
            yield conn
    finally:
        conn.close()

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
                session_name TEXT,
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

        cur.execute('''
            CREATE TABLE IF NOT EXISTS friendships (
                friendship_id SERIAL PRIMARY KEY,
                requester_id INTEGER NOT NULL,
                addressee_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'accepted')),
                created_at TEXT NOT NULL,
                responded_at TEXT NULL,
                CHECK (requester_id <> addressee_id),
                FOREIGN KEY (requester_id) REFERENCES users(user_id),
                FOREIGN KEY (addressee_id) REFERENCES users(user_id)
            );
        ''')

        # One row per pair regardless of who asked, so B cannot request A while
        # A's request to B is still pending.
        cur.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_friendship_unique_pair
            ON friendships (LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id));
        ''')

        conn.commit()

def db_create_session(conn, user_id, session_name, performed_at, notes) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (user_id, session_name, performed_at, ended_at, notes) VALUES (%s, %s, %s, %s, %s) RETURNING session_id;",
        (user_id, session_name, performed_at, None, notes)
    )
    session_id = cur.fetchone()[0]
    return session_id

def db_end_all_open_sessions(conn, user_id: int, ended_at: str, session_name: str = None) -> int:
    cur = conn.cursor()
    cur.execute("""
        UPDATE sessions
        SET ended_at = %s, session_name = COALESCE(%s, session_name)
        WHERE user_id = %s AND ended_at IS NULL
    """, (ended_at, session_name, user_id))
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
        SELECT session_id, session_name FROM sessions
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
        SELECT session_id, user_id, performed_at, notes, ended_at, session_name
        FROM sessions
        WHERE user_id = %s AND ended_at IS NULL
        LIMIT 1;
    """, (user_id,))
    return cur.fetchone()

def db_get_session_owner(conn, session_id: int) -> Optional[int]:
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM sessions WHERE session_id = %s;", (session_id,))
    row = cur.fetchone()
    return row[0] if row else None

def db_get_sessions_for_user(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT session_id, session_name, user_id, performed_at, notes, ended_at
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

def db_get_user_by_username(conn, username: str):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id, username FROM users WHERE username = %s;", (username,))
    return cur.fetchone()

def db_get_user_by_id(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id, username FROM users WHERE user_id = %s;", (user_id,))
    return cur.fetchone()

def db_search_users(conn, query: str, searcher_id: int, limit: int = 10):
    '''
    Substring match on username, excluding the searcher. Carries each result's
    relationship to the searcher so the UI knows which button to draw, without
    a follow-up query per row.
    '''
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT users.user_id,
               users.username,
               CASE
                 WHEN friendships.friendship_id IS NULL THEN 'none'
                 WHEN friendships.status = 'accepted' THEN 'friends'
                 WHEN friendships.requester_id = %s THEN 'request_sent'
                 ELSE 'request_received'
               END AS status
        FROM users
        LEFT JOIN friendships
          ON (friendships.requester_id = users.user_id AND friendships.addressee_id = %s)
          OR (friendships.addressee_id = users.user_id AND friendships.requester_id = %s)
        WHERE users.username ILIKE %s AND users.user_id <> %s
        ORDER BY users.username
        LIMIT %s;
    """, (searcher_id, searcher_id, searcher_id, f"%{query}%", searcher_id, limit))
    return cur.fetchall()

# FRIENDSHIPS

def db_create_friend_request(conn, requester_id: int, addressee_id: int, created_at: str) -> int:
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO friendships (requester_id, addressee_id, status, created_at, responded_at)
        VALUES (%s, %s, 'pending', %s, NULL) RETURNING friendship_id;
    """, (requester_id, addressee_id, created_at))
    return cur.fetchone()[0]

def db_get_friendship_between(conn, user_a: int, user_b: int):
    '''the pair's row in either direction, whatever its status'''
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT friendship_id, requester_id, addressee_id, status, created_at, responded_at
        FROM friendships
        WHERE (requester_id = %s AND addressee_id = %s)
           OR (requester_id = %s AND addressee_id = %s);
    """, (user_a, user_b, user_b, user_a))
    return cur.fetchone()

def db_get_friendship(conn, friendship_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT friendship_id, requester_id, addressee_id, status, created_at, responded_at
        FROM friendships WHERE friendship_id = %s;
    """, (friendship_id,))
    return cur.fetchone()

def db_accept_friend_request(conn, friendship_id: int, responded_at: str) -> int:
    cur = conn.cursor()
    cur.execute("""
        UPDATE friendships SET status = 'accepted', responded_at = %s
        WHERE friendship_id = %s AND status = 'pending';
    """, (responded_at, friendship_id))
    return cur.rowcount

def db_delete_friendship(conn, friendship_id: int) -> int:
    '''used for declining, cancelling, and unfriending'''
    cur = conn.cursor()
    cur.execute("DELETE FROM friendships WHERE friendship_id = %s;", (friendship_id,))
    return cur.rowcount

def db_are_friends(conn, user_a: int, user_b: int) -> bool:
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM friendships
        WHERE status = 'accepted'
          AND ((requester_id = %s AND addressee_id = %s)
            OR (requester_id = %s AND addressee_id = %s));
    """, (user_a, user_b, user_b, user_a))
    return cur.fetchone() is not None

def db_get_friends(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT friendships.friendship_id,
               users.user_id AS friend_id,
               users.username,
               friendships.responded_at
        FROM friendships
        JOIN users ON users.user_id = CASE
            WHEN friendships.requester_id = %s THEN friendships.addressee_id
            ELSE friendships.requester_id
        END
        WHERE friendships.status = 'accepted'
          AND %s IN (friendships.requester_id, friendships.addressee_id)
        ORDER BY users.username;
    """, (user_id, user_id))
    return cur.fetchall()

def db_get_incoming_requests(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT friendships.friendship_id,
               users.user_id AS friend_id,
               users.username,
               friendships.created_at
        FROM friendships
        JOIN users ON users.user_id = friendships.requester_id
        WHERE friendships.addressee_id = %s AND friendships.status = 'pending'
        ORDER BY friendships.created_at DESC;
    """, (user_id,))
    return cur.fetchall()

def db_get_outgoing_requests(conn, user_id: int):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT friendships.friendship_id,
               users.user_id AS friend_id,
               users.username,
               friendships.created_at
        FROM friendships
        JOIN users ON users.user_id = friendships.addressee_id
        WHERE friendships.requester_id = %s AND friendships.status = 'pending'
        ORDER BY friendships.created_at DESC;
    """, (user_id,))
    return cur.fetchall()

def db_get_sets_for_exercise(conn, user_id: int, exercise: str):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT sets.set_id, sets.weight, sets.reps, sets.is_1rm, sets.session_id, sessions.performed_at
        FROM sets
        JOIN sessions ON sets.session_id = sessions.session_id
        WHERE sessions.user_id = %s AND sets.exercise = %s
        ORDER BY sessions.performed_at ASC;
    """, (user_id, exercise))
    return cur.fetchall()