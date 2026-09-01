import sqlite3
from datetime import datetime

import bcrypt

from src.repository.db import (
    get_conn,
    db_create_user,
    db_get_user,
    db_create_session,
    db_get_active_session,
    db_end_all_open_sessions,
    db_insert_sets,
    db_get_active_session_row,
    db_get_sessions_for_user,
    db_get_active_session,
    db_get_sets_for_session, db_get_exercises_for_user, db_get_sets_for_exercise,
    db_get_user_by_username,
    db_get_user_by_id,
    db_search_users,
    db_create_friend_request,
    db_get_friendship_between,
    db_get_friendship,
    db_accept_friend_request,
    db_delete_friendship,
    db_are_friends,
    db_get_friends,
    db_get_incoming_requests,
    db_get_outgoing_requests,
    db_get_session_owner,
)
from src.api.auth import issue_token
from src.services.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def create_user(username: str, password: str) -> dict:
    created_at = now_iso()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_conn() as conn:
        # if exists, treat as conflict
        existing = db_get_user(conn, username)
        if existing is not None:
            raise ConflictError("Username already taken.")

        user_id = db_create_user(conn, created_at, username, password_hash)
        conn.commit()
    return {
        "user_id": user_id,
        "username": username,
        "created_at": created_at,
        "access_token": issue_token(user_id),
    }

def login_user(username: str, password: str) ->dict:
    with get_conn() as conn:
        row = db_get_user(conn, username)
        if row is None:
            raise NotFoundError("No account found with that username.")
        user_id, password_hash = row["user_id"], row["password_hash"]
        if not bcrypt.checkpw(password.encode(), password_hash.encode()):
            raise BadRequestError("Password incorrect.")
        return {
            "user_id": user_id,
            "username": username,
            "access_token": issue_token(user_id),
        }


def create_session(user_id: int, session_name: str, performed_at: str | None, notes :str | None) -> dict:
    performed_at = performed_at or now_iso()

    # Use custom name if provided, otherwise generate from date
    if not session_name:
        date_str = datetime.fromisoformat(performed_at).strftime("%m-%d-%Y")
        session_name = f"Session {date_str}"

    with get_conn() as conn:
        active = db_get_active_session(conn, user_id)
        if active is not None:
            raise ConflictError("Active session already exists")
        session_id = db_create_session(conn, user_id, session_name, performed_at, notes)
        conn.commit()

    return {
        "session_id": session_id,
        "session_name": session_name,
        "user_id": user_id,
        "performed_at": performed_at,
        "notes": notes,
        "ended_at": None,
    }

def end_active_session(user_id: int, session_name: str = None) -> dict:
    ended_at = now_iso()
    with get_conn() as conn:
        n = db_end_all_open_sessions(conn, user_id, ended_at, session_name)
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

# for GET requests

def get_user(user_id: int) -> dict:
    with get_conn() as conn:
        row = db_get_user_by_id(conn, user_id)
        if row is None:
            raise NotFoundError("User not found")
        return dict(row)

def get_active_session(user_id: int):
    with get_conn() as conn:
        row = db_get_active_session_row(conn, user_id)

        if row is None:
            raise NotFoundError("No active session found for this user")

        return dict(row)

def get_sessions_for_user(user_id: int):
    with get_conn() as conn:
        rows = db_get_sessions_for_user(conn, user_id)

        if rows is None:
            raise NotFoundError("No active sessions found for this user")

        return [dict(r) for r in rows]

def get_sets_for_session(user_id: int, session_id: int):
    with get_conn() as conn:
        # session ids are guessable, so confirm the caller owns this one
        owner_id = db_get_session_owner(conn, session_id)
        if owner_id is None:
            raise NotFoundError("Session not found")
        if owner_id != user_id:
            raise ForbiddenError("That session belongs to another user")

        rows = db_get_sets_for_session(conn, session_id)

        if rows is None:
            return []

        return [dict(r) for r in rows]

def get_exercises_for_user(user_id: int):
    with get_conn() as conn:
        rows = db_get_exercises_for_user(conn, user_id)

        if rows is None:
            return []

        return [row["exercise"] for row in rows]

def get_sets_for_exercise(user_id: int, exercise: str):
    with get_conn() as conn:
        rows = db_get_sets_for_exercise(conn, user_id, exercise)
        return [dict(r) for r in rows]

# SOCIAL / FRIENDSHIPS

def search_users(user_id: int, query: str, limit: int = 10):
    query = query.strip()
    if not query:
        return []

    with get_conn() as conn:
        # each row carries status: none | friends | request_sent | request_received
        return [dict(r) for r in db_search_users(conn, query, user_id, limit)]

def send_friend_request(user_id: int, username: str) -> dict:
    username = username.strip()
    if not username:
        raise BadRequestError("Username cannot be empty")

    with get_conn() as conn:
        target = db_get_user_by_username(conn, username)
        if target is None:
            raise NotFoundError("No account found with that username.")

        addressee_id = target["user_id"]
        if addressee_id == user_id:
            raise BadRequestError("You cannot send a friend request to yourself")

        existing = db_get_friendship_between(conn, user_id, addressee_id)
        if existing is not None:
            if existing["status"] == "accepted":
                raise ConflictError(f"You are already friends with {username}")
            if existing["requester_id"] == user_id:
                raise ConflictError(f"You already have a pending request to {username}")
            raise ConflictError(f"{username} already sent you a request — accept it instead")

        friendship_id = db_create_friend_request(conn, user_id, addressee_id, now_iso())
        conn.commit()

    return {
        "friendship_id": friendship_id,
        "friend_id": addressee_id,
        "username": username,
        "status": "pending",
    }

def respond_to_friend_request(user_id: int, friendship_id: int, accept: bool) -> dict:
    with get_conn() as conn:
        row = db_get_friendship(conn, friendship_id)
        if row is None:
            raise NotFoundError("Friend request not found")
        # only the person who received it gets to answer it
        if row["addressee_id"] != user_id:
            raise ForbiddenError("You cannot respond to this friend request")
        if row["status"] != "pending":
            raise ConflictError("That friend request has already been accepted")

        if accept:
            db_accept_friend_request(conn, friendship_id, now_iso())
            status = "accepted"
        else:
            # declining drops the row so either side can ask again later
            db_delete_friendship(conn, friendship_id)
            status = "declined"
        conn.commit()

    return {"friendship_id": friendship_id, "status": status}

def cancel_friend_request(user_id: int, friendship_id: int) -> dict:
    with get_conn() as conn:
        row = db_get_friendship(conn, friendship_id)
        if row is None:
            raise NotFoundError("Friend request not found")
        if row["requester_id"] != user_id:
            raise ForbiddenError("You cannot cancel this friend request")
        if row["status"] != "pending":
            raise ConflictError("That request was already accepted — remove the friend instead")

        db_delete_friendship(conn, friendship_id)
        conn.commit()

    return {"friendship_id": friendship_id, "status": "cancelled"}

def remove_friend(user_id: int, friend_id: int) -> dict:
    with get_conn() as conn:
        row = db_get_friendship_between(conn, user_id, friend_id)
        if row is None or row["status"] != "accepted":
            raise NotFoundError("You are not friends with that user")

        db_delete_friendship(conn, row["friendship_id"])
        conn.commit()

    return {"friend_id": friend_id, "status": "removed"}

def get_friends(user_id: int):
    with get_conn() as conn:
        return [dict(r) for r in db_get_friends(conn, user_id)]

def get_friend_requests(user_id: int):
    with get_conn() as conn:
        return {
            "incoming": [dict(r) for r in db_get_incoming_requests(conn, user_id)],
            "outgoing": [dict(r) for r in db_get_outgoing_requests(conn, user_id)],
        }

def _require_friendship(conn, user_id: int, friend_id: int):
    if user_id == friend_id:
        return
    if not db_are_friends(conn, user_id, friend_id):
        raise ForbiddenError("You can only view lifts for your friends")

def get_friend_exercises(user_id: int, friend_id: int):
    with get_conn() as conn:
        _require_friendship(conn, user_id, friend_id)
        if db_get_user_by_id(conn, friend_id) is None:
            raise NotFoundError("User not found")
        return [row["exercise"] for row in db_get_exercises_for_user(conn, friend_id)]

def get_friend_sets_for_exercise(user_id: int, friend_id: int, exercise: str):
    with get_conn() as conn:
        _require_friendship(conn, user_id, friend_id)
        rows = db_get_sets_for_exercise(conn, friend_id, exercise)
        return [dict(r) for r in rows]