"""
Token authentication for Lift Log.

Login issues a signed JWT; every protected route resolves the caller from that
token via the `current_user_id` dependency. Routes never accept a user id as
input, so a client cannot act as another user by editing a URL.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=7)

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    # Fail at import rather than fall back to a default: a predictable secret
    # means anyone can mint a token for any account.
    raise RuntimeError(
        "JWT_SECRET is not set. Generate one with "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"` "
        "and export it before starting the API."
    )

security = HTTPBearer()

def issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def current_user_id(creds: HTTPAuthorizationCredentials = Depends(security)) -> int:
    '''FastAPI dependency: the authenticated caller's user_id, or 401.'''
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Session expired — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
