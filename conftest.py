"""
Test configuration.

Tests run against a real PostgreSQL database so the schema and queries are
exercised as written. The database is truncated between tests, so it must never
be a database anyone cares about — see `_assert_local` below.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://localhost/lift_log_test"
)

def _assert_local(url: str) -> None:
    '''
    Refuse to run against a remote host. These tests TRUNCATE every table, so a
    stray DATABASE_URL pointing at the deployed database would wipe real data.
    '''
    host = urlparse(url).hostname or "localhost"
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(
            f"Refusing to run tests against non-local database host {host!r}. "
            "Set TEST_DATABASE_URL to a local scratch database."
        )

# Set before any test module is imported: src.api.auth reads JWT_SECRET at
# import time, and collection happens before fixtures run.
_assert_local(TEST_DATABASE_URL)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

TABLES = ("friendships", "sets", "sessions", "users")

@pytest.fixture(scope="session", autouse=True)
def initialized_schema():
    from src.repository.db import db_init_db
    db_init_db()
    yield

@pytest.fixture(autouse=True)
def clean_tables(initialized_schema):
    '''Every test starts from an empty database with ids restarting at 1.'''
    from src.repository.db import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE;")
        conn.commit()
    yield

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from src.api.main import app
    with TestClient(app) as c:
        yield c

@pytest.fixture
def make_user(client):
    '''Registers a user and returns their details plus an auth header.'''
    def _make(username: str = "sherman", password: str = "hunter22") -> dict:
        res = client.post("/users", json={"username": username, "password": password})
        assert res.status_code == 201, res.text
        data = res.json()
        return {
            **data,
            "password": password,
            "auth": {"Authorization": f"Bearer {data['access_token']}"},
        }
    return _make
