'''
functions to execute each menu option
'''

import sqlite3
from pathlib import Path
from datetime import datetime
from db import (db_end_all_open_sessions, db_create_session, db_get_next_set_index,
                db_insert_sets, db_get_conn, DB_PATH, db_get_active_session, db_get_sets_by_session)
from services import parse_entry_line, parse_set_token
from typing import Callable

from src.db import db_get_sets_by_session

# CONSTANT for main menu
MENU_TEXT = """
    Select from the following options:
        1) Start new session
	    2) Add sets to active session
	    3) View session
	    4) View exercise stats
	    5) List sessions
	    6) End active session
	    7) Exit
	"""
VALID_OPTIONS = (1, 2, 3, 4, 5, 6, 7)

# menu choices
# 1) start new session
def start_new_session(user_id: int, notes=None) -> int:
    performed_at = datetime.now().isoformat(timespec="seconds")

    with db_get_conn() as conn:
        # end any existing active sessions & start new one
        closed_sessions = db_end_all_open_sessions(conn, user_id, performed_at)
        if closed_sessions > 0:
            print(f"{closed_sessions} sessions closed.")
        session_id = db_create_session(conn, user_id, performed_at, notes)

    print(f"new session started. session id: {session_id}")
    return session_id

# 2) add set

def add_set_ui(user_id):
    session_id = db_get_active_session(user_id)

    if session_id is None:
        print("No active session.")
        return

    raw = input("Enter sets (e.g., bench press: 135x5, 155x3: ").strip()

    try:
        exercise, tokens = parse_entry_line(raw)
        rows = []
        for token in tokens:
            weight, reps = parse_set_token(token)
            is_1rm = 0
            if reps == 1:
                ans = input(f"Mark {exercise} at {weight} lb as tested 1RM? (y/n): ").strip().lower()
                while ans not in ("y", "n"):
                    ans = input("y/n: ").strip().lower()
                is_1rm = 1 if ans == "y" else 0
            rows.append((weight, reps, is_1rm))

        conn = db_get_conn()
        try:
            n = db_insert_sets(conn, session_id, exercise, rows)
            conn.commit()
            print(f"{n} sets added for '{exercise}'.")
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {e}")
        finally:
            conn.close()

    except ValueError as e:
        print(e)

# 3) view active session
def view_active_session(user_id):
    session_id = db_get_active_session(user_id)

    if session_id is None:
        print("No active session.")
        return

    sets = db_get_sets_by_session(session_id)
    for row in sets:
        rm_statement = ""
        if row[4] == 1:
            rm_statement = "*TESTED 1RM*"

        print(f"{row[0]}: {row[1]} lbs {row[2]} reps {rm_statement}.")

# 4) View exercise stats
def view_stats(user_id):
    exercise = input('provide exercise to view stats for: ').strip().lower()
    if not exercise:
        print("No exercise provided.")
        return

    with db_get_conn() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT s.weight, s.reps, s.is_1rm
            FROM sets s
            JOIN sessions sess ON sess.session_id = s.session_id
            WHERE sess.user_id = ?
            AND lower(s.exercise) = ?
            ORDER BY s.weight DESC
            ''', (user_id, exercise,))

        rows = cursor.fetchall()
        if not rows:
            print(f"No sets found for exercise {exercise}.")
            return

        print(f"{exercise} stats:")
        print(f"--> {len(rows)} sets completed")

        max_weight, max_reps, _ = rows[0]
        print(f"--> {max_weight} lb max weight at {max_reps} reps")

        # look for 1RM if exists
        cursor.execute('''
            SELECT s.weight, s.reps
            FROM sets s
            JOIN sessions sess ON sess.session_id = s.session_id
            WHERE sess.user_id = ?
            AND lower(s.exercise) = ?
            AND s.is_1rm = 1
            ORDER BY s.weight DESC
            LIMIT 1
            ''', (user_id, exercise,))

        one_rm = cursor.fetchone()
        if one_rm is not None:
            print(f"--> Tested 1RM at {one_rm[0]} lb")
        else:
            print("No tested 1RM")

# 5) list sessions
def view_sessions(user_id):
    with db_get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT session_id, performed_at
            FROM sessions
            WHERE user_id = ?
            ORDER BY session_id DESC
            ''', (user_id,))
        rows = cursor.fetchall()
        if not rows:
            print(f"No sessions found for user {user_id}.")
            return
        print(f"{len(rows)} sessions completed.")
        for row in rows:
            print(f"session {row[0]} completed [{row[1]}]")

# 6) end active session
def end_active_session(user_id):
    with db_get_conn() as conn:
        cursor = conn.cursor()
        ended_at = datetime.now().isoformat(timespec="seconds")

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
            print("No active session.")
            return

        session_id = row[0]

        cursor.execute(
            """UPDATE sessions
            SET ended_at = ?
            WHERE session_id = ?
            """,
            (ended_at, session_id)
        )
        conn.commit()
        print(f"Ended session {session_id} at {ended_at}.")

# 7) closeout
def closeout(user_id):
    session_id = db_get_active_session(user_id)

    if session_id is not None:
        choice = input("end active session before exiting? (y/n): ").strip().lower()
        if choice == 'y':
            end_active_session(session_id)
        elif choice == 'n':
            print('session not ended')
    choice = input('Are you sure you want to quit? (y/n): ').strip().lower()

    while choice != 'y' and choice != 'n':
        choice = input('y/n: ').strip().lower()

    if choice == 'y':
        print('goodbye!')
        return True

    else:
        return False


# UI functions
def get_username():
    accepted = False
    raw = input("Enter username: ")
    while not accepted:
        if raw.strip(" ") != "":
            accepted = True
        else:
            raw = input("Empty string not accepted. Enter username: ")

    username = normalize_username(raw)
    return username

def get_menu_choice() -> int:
    choice = input(MENU_TEXT)
    try:
        choice = int(choice)
    except:
        print('choice must be 1-7')
        choice = get_menu_choice()

    if choice not in VALID_OPTIONS:
        choice = get_menu_choice()
    return choice

def normalize_username(raw: str) -> str:
    return " ".join(raw.strip().lower().split())

def get_or_create_user(username: str) -> int:
    username = normalize_username(username)
    created_at = datetime.now().isoformat(timespec="seconds")

    conn = db_get_conn()
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM users WHERE username = ?;", (username,))
    row = cur.fetchone()
    if row is not None:
        conn.close()
        return row[0]

    cur.execute(
        "INSERT INTO users (username, created_at) VALUES (?, ?);",
        (username, created_at)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id
