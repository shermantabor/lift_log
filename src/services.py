"""
Business logic for Lift Log.

Provides higher-level operations that coordinate between the
database layer and user-facing workflows.
"""

from typing import Callable
import sqlite3
from datetime import datetime
from db import db_insert_sets, get_conn, db_get_active_session, db_create_user, db_get_user

SetRow = tuple[float, int, int] # (weight, reps, is_1rm)
# CONSTANTS for main menu
MENU_TEXT = """
    Select from the following options:
        1) Start new session
	    2) Add sets to active session
	    3) View active session
	    4) View exercise stats
	    5) List sessions
	    6) End active session
	    7) Exit
	"""
VALID_OPTIONS = (1, 2, 3, 4, 5, 6, 7)

class NoActiveSessionError(Exception):
    pass

def add_sets_from_entry(
        user_id: int,
        raw_entry: str,
        *,
        ask_is_1rm: Callable[[str, float], bool],
    ) -> tuple[str, int]:
    '''
    Business logic:
    - requires active session
    - parses entry line and set tokens
    - for reps == 1, asks user whether to mark as tested 1RM
    - writes to db
    Returns (exercise, num_sets_inserted)
    '''

    # check whether there is currently an active session
    with get_conn() as conn:
        session_id = db_get_active_session(conn, user_id)
        if session_id is None:
            raise NoActiveSessionError()

        # given active session, convert raw entry into data
        exercise, tokens = parse_entry_line(raw_entry)

        rows: list[SetRow] = []
        for token in tokens:
            weight, reps = parse_set_token(token)
            is_1rm = 0
            if reps == 1 and ask_is_1rm(exercise, weight):
                is_1rm = 1
            rows.append((weight, reps, is_1rm))

        # insert set data into db
        try:
            db_insert_sets(conn, session_id, exercise, rows)
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise

    return exercise, len(rows)

def normalize_exercise(name: str) -> str:
    '''clean up exercise name'''
    return " ".join(name.strip().lower().split())

def parse_entry_line(raw: str) -> tuple[str, list[str]]:
    '''
    I: raw set entry
    P: check for valid entry, parse into usable data
    R: ('exercise name', ['weightxreps', 'weightxreps', ...])
    '''

    # split exercise name from numerical data
    parts = raw.split(":", 1)
    if len(parts) != 2:
        raise ValueError("Expected ':' after exercise name")

    exercise = normalize_exercise(parts[0])
    if not exercise:
        raise ValueError("Exercise name is missing")

    tokens = [t.strip() for t in parts[1].split(",") if t.strip()]
    if not tokens:
        raise ValueError("No sets provided")

    return exercise, tokens

def parse_set_token(token: str) -> tuple[float, int]:
    '''
    I: list of 'weightxreps'
    O: weight (float), reps (int)
    '''
    parts = token.split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid set '{token}'. Expected weightxreps")

    try:
        weight = float(parts[0].strip())
        reps = int(parts[1].strip())

    except ValueError:
        raise ValueError(f"Invalid numbers in set '{token}'")

    if weight < 0 or reps <= 0:
        raise ValueError(f"Weight and reps must be positive in '{token}'")

    return weight, reps

# UI functions
def get_username():
    '''
    ask for username
    '''
    while True:
        raw = input("Enter username: ")
        if raw.strip(" ") != "":
            username = normalize_username(raw)
            return username
        print("Empty string not accepted.")

def get_menu_choice() -> int:
    '''
    ask for menu choice
    '''
    while True:
        choice = input(MENU_TEXT)
        if choice in ('1', '2', '3', '4', '5', '6', '7'):
            return int(choice)
        print("choice must be 1-7")

def normalize_username(raw: str) -> str:
    return " ".join(raw.strip().lower().split())

def get_or_create_user(username: str) -> int:
    '''
    I: username
    P:  (1) if user already exists, return user ID
        (2) if user does not exist, create and return user ID
    O: user ID
    '''
    username = normalize_username(username)
    created_at = datetime.now().isoformat(timespec="seconds")

    # check whether user exists
    conn = get_conn()
    user_id = db_get_user(conn, username)
    if user_id is not None:
        return user_id

    # create new user
    user_id = db_create_user(conn, created_at, username)
    conn.commit()
    conn.close()
    return user_id