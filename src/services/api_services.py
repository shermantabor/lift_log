import sqlite3
from datetime import datetime

from src.repository.db import (
    get_conn,
    db_create_user,
    db_get_user,
    db_create_session,
    db_get_active_session,
    db_end_all_open_sessions,
    db_insert_sets,
)
from src.services.errors import BadRequestError, ConflictError


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def create_user(username: str) -> dict:
    created_at = now_iso()
    with get_conn() as conn:
        # if exists, treat as conflict
        existing = db_get_user(conn, username)
        if existing is not None:
            raise ConflictError("User already exists with this username")

        user_id = db_create_user(conn, created_at, username)
        conn.commit()
    return {"user_id": user_id, "username": username, "created_at": created_at}

def create_session(user_id: int, performed_at: str | None, notes :str | None) -> dict:
    performed_at = performed_at or now_iso()

    with get_conn() as conn:
        active = db_get_active_session(conn, user_id)
        if active is not None:
            raise ConflictError("Active session already exists")
        session_id = db_create_session(conn, user_id, performed_at, notes)
        conn.commit()

    return {
        "session_id": session_id,
        "user_id": user_id,
        "performed_at": performed_at,
        "notes": notes,
        "ended_at": None,
    }

def end_active_session(user_id: int) -> dict:
    ended_at = now_iso()
    with get_conn() as conn:
        n = db_end_all_open_sessions(conn, user_id, ended_at)
        if n == 0:
            raise BadRequestError("No active session found for this user")
        conn.commit()

    return {"user_id": user_id, "ended_at": ended_at, "ended_sessions": n}

def normalize_exercise(name:str) -> str:
    return " ".join(name.strip().lower().split())

def add_sets_to_active_session(
        user_id: int,
        exercise: str,
        sets: list[tuple[float, int, int]]
) -> dict:
    exercise_norm = normalize_exercise(exercise)

    if not exercise_norm:
        raise BadRequestError("Exercise name cannot be empty")

    if not sets:
        raise BadRequestError("must provide at least one set")

    with get_conn() as conn:
        session_id = db_get_active_session(conn, user_id)
        if session_id is None:
            raise BadRequestError("No active session found for this user")

        try:
            inserted = db_insert_sets(conn, session_id, exercise_norm, sets)
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(
                "Set insert failed due to a constraint (possible duplicate ordering or invalid values)"
            ) from e

    return {"session_id": session_id, "exercise": exercise_norm, "sets_inserted": inserted}


