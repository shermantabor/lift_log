"""
Tests for token issue/verify.

These exercise the auth layer only, so unlike the API tests they need no
database — just JWT_SECRET set in the environment.
"""

import datetime

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.auth import issue_token, current_user_id, JWT_SECRET, ALGORITHM

def verify(token: str) -> int:
    return current_user_id(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token))

def make_token(payload: dict, secret: str = JWT_SECRET, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)

def future(**kwargs) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(**kwargs)

def test_round_trip():
    assert verify(issue_token(42)) == 42

def test_token_carries_expiry():
    payload = jwt.decode(issue_token(1), JWT_SECRET, algorithms=[ALGORITHM])
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]

def test_rejects_token_signed_with_another_secret():
    forged = make_token({"sub": "1", "exp": future(days=1)}, secret="not-the-real-secret")
    with pytest.raises(HTTPException) as exc:
        verify(forged)
    assert exc.value.status_code == 401

def test_rejects_expired_token():
    expired = make_token({"sub": "42", "exp": future(seconds=-1)})
    with pytest.raises(HTTPException) as exc:
        verify(expired)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()

def test_rejects_unsigned_token():
    '''the classic alg=none downgrade must not be accepted'''
    unsigned = jwt.encode({"sub": "1"}, "", algorithm="none")
    with pytest.raises(HTTPException) as exc:
        verify(unsigned)
    assert exc.value.status_code == 401

def test_rejects_malformed_token():
    with pytest.raises(HTTPException) as exc:
        verify("not-a-jwt")
    assert exc.value.status_code == 401

def test_rejects_token_without_subject():
    no_sub = make_token({"exp": future(days=1)})
    with pytest.raises(HTTPException) as exc:
        verify(no_sub)
    assert exc.value.status_code == 401
