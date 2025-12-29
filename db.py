'''
functions to interact with db
'''

from pathlib import Path
import sqlite3
from datetime import datetime
from typing import Optional, Iterable, Sequence, Tuple

# ensure data directory exists and use ABSOLUTE path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "lift_log.db"

SetRow = tuple[float, int, int] # (weight, reps, is_1rm)

def db_init_db():
    # connect to the database (creates file if DNE)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # create user data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
    ''')

    # create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            performed_at TEXT NOT NULL,
            notes TEXT,
            ended_at TEXT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    ''')

    # enforce only one active session
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_session_per_user
        ON sessions (user_id)
        WHERE ended_at IS NULL;
        ''')

    # create sets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sets (
            set_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise TEXT NOT NULL,
            weight REAL NOT NULL CHECK(weight >= 0),
            reps INTEGER NOT NULL CHECK(reps > 0),
            set_index INTEGER NOT NULL CHECK(set_index > 0),
            is_1rm INTEGER NOT NULL CHECK(is_1rm IN (0, 1)),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
    ''')

    # enforce unique set id
    cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sets_unique_order
            ON sets(session_id, exercise, set_index);
            ''')

    # commit changes and close
    conn.commit()
    conn.close()

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def db_create_session(conn, user_id, performed_at, notes) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (user_id, performed_at, ended_at, notes) VALUES (?, ?, ?, ?);",
        (user_id, performed_at, None, notes)
    )
    session_id = cur.lastrowid
    return session_id

def db_end_all_open_sessions(conn, user_id: int, performed_at: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sessions
        SET ended_at = ?
        WHERE user_id = ?
        AND ended_at IS NULL
        """,
        (performed_at, user_id)
    )
    return cur.rowcount

def db_get_next_set_index(conn, session_id: int, exercise: str) -> int:
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(set_index), 0) FROM sets WHERE session_id = ? AND exercise = ?",
        (session_id, exercise)
    )
    return cur.fetchone()[0] + 1

def db_insert_sets(conn, session_id, exercise, rows: Sequence[SetRow]) -> int:
    '''insert multiple sets for given session/exercise
    return number of rows inserted
    '''

    # need to make set_index increment!!

    start_index = db_get_next_set_index(conn, session_id, exercise)
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO sets (session_id, exercise, weight, reps, is_1rm, set_index) 
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (session_id, exercise, weight, reps, is_1rm, start_index + i)
            for i, (weight, reps, is_1rm) in enumerate(rows)
        ],
    )

    return cur.rowcount

def db_get_active_session(conn, user_id: int) -> Optional[int]:
    cursor = conn.cursor()

    # find the latest session and make sure it's not ended
    cursor.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE user_id = ?
        AND ended_at IS NULL
        ORDER BY session_id DESC
        LIMIT 1
        """,
        (user_id,)
    )

    row = cursor.fetchone()
    if row is None:
        return None

    session_id = row[0]

    return session_id

def db_get_sets_by_session(conn, session_id: int) -> tuple[str, float, int, int, int]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT set_id, exercise, weight, reps, is_1rm
        FROM sets
        WHERE session_id = ?
        ORDER BY set_id DESC
        """,
        (session_id,)
    )

    rows = cursor.fetchall()
    return rows