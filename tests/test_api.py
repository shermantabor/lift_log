import tempfile
import pytest
from fastapi.testclient import TestClient
import src

from src.api.main import app
from src.repository import db

@pytest.fixture
def client():
    with tempfile.NamedTemporaryFile() as tmp:
        db.TEST_DB_PATH = tmp.name
        db.db_init_db()

        client = TestClient(app)
        yield client

        db.TEST_DB_PATH = None

def test_create_user(client):
    res = client.post("/users", json={"username": "sherman"})
    assert res.status_code == 201
    data = res.json()
    assert "user_id" in data
    assert data["username"] == "sherman"

def test_duplicate_username(client):
    client.post("/users", json={"username": "sherman"})
    res = client.post("/users", json={"username": "sherman"})
    assert res.status_code == 409

def test_create_session(client):
    user = client.post("/users", json={"username": "sherman"}).json()
    res = client.post(f"/users/{user['user_id']}/sessions", json={})
    assert res.status_code == 201

def test_only_one_active_session(client):
    user = client.post("/users", json={"username": "sherman"}).json()
    client.post(f"/users/{user['user_id']}/sessions", json={})
    res = client.post(f"/users/{user['user_id']}/sessions", json={})
    assert res.status_code == 409

def test_add_sets(client):
    user = client.post("/users", json={"username": "sherman"}).json()
    client.post(f"/users/{user['user_id']}/sessions", json={})

    payload = {
        "sets": [
            {"exercise": "bench press", "weight": 225, "reps": 5},
            {"exercise": "bench press", "weight": 225, "reps": 5},
        ]
    }

    res = client.post(f"/users/{user['user_id']}/sets", json=payload)
    assert res.status_code == 201
    assert res.json()["sets_inserted"] == 2

def test_add_sets_without_session(client):
    user = client.post("/users", json={"username": "sherman"}).json()

    payload = {
        "sets": [
            {"exercise": "bench press", "weight": 225, "reps": 5}
        ]
    }

    res = client.post(f"/users/{user['user_id']}/sets", json=payload)
    assert res.status_code == 400

def test_mixed_exercise_batch(client):
    user = client.post("/users", json={"username": "sherman"}).json()
    client.post(f"/users/{user['user_id']}/sessions", json={})

    payload = {
        "sets": [
            {"exercise": "bench press", "weight": 225, "reps": 5},
            {"exercise": "squat", "weight": 315, "reps": 5},
        ]
    }

    res = client.post(f"/users/{user['user_id']}/sets", json=payload)
    assert res.status_code == 400