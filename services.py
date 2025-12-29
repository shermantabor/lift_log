'''
services: no UI, orchestrates DB calls
'''

from typing import Callable, Tuple, Optional
import sqlite3
from db import db_insert_sets, get_conn, db_get_active_session

SetRow = tuple[float, int, int] # (weight, reps, is_1rm)

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

    with get_conn() as conn:
        session_id = db_get_active_session(conn, user_id)
        if session_id is None:
            raise NoActiveSessionError()

        exercise, tokens = parse_entry_line(raw_entry)

        rows: list[SetRow] = []
        for token in tokens:
            weight, reps = parse_set_token(token)
            is_1rm = 0
            if reps == 1 and ask_is_1rm(exercise, weight):
                is_1rm = 1
            rows.append((weight, reps, is_1rm))

        try:
            db_insert_sets(conn, session_id, exercise, rows)
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise

    return exercise, len(rows)

def normalize_exercise(name: str) -> str:
    return " ".join(name.strip().lower().split())

def parse_entry_line(raw: str) -> tuple[str, list[str]]:
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