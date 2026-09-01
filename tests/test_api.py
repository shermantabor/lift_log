"""
Core API tests: registration, login, sessions, and sets.

Fixtures (`client`, `make_user`) and the per-test database reset live in the
root conftest.py.
"""

def auth_of(user):
    return user["auth"]

# REGISTRATION & LOGIN

def test_register_returns_token(client):
    res = client.post("/users", json={"username": "sherman", "password": "hunter22"})
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "sherman"
    assert data["access_token"]
    assert data["token_type"] == "bearer"

def test_duplicate_username(client, make_user):
    make_user("sherman")
    res = client.post("/users", json={"username": "sherman", "password": "another1"})
    assert res.status_code == 409

def test_login_returns_token(client, make_user):
    user = make_user("sherman", "hunter22")
    res = client.post("/login", json={"username": "sherman", "password": "hunter22"})
    assert res.status_code == 200
    assert res.json()["user_id"] == user["user_id"]
    assert res.json()["access_token"]

def test_login_wrong_password(client, make_user):
    make_user("sherman", "hunter22")
    res = client.post("/login", json={"username": "sherman", "password": "wrongpass"})
    assert res.status_code == 401

def test_login_unknown_user(client):
    res = client.post("/login", json={"username": "nobody", "password": "hunter22"})
    assert res.status_code == 404

def test_password_is_not_stored_in_plaintext(client, make_user):
    from src.repository.db import get_conn
    make_user("sherman", "hunter22")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = 'sherman';")
        stored = cur.fetchone()[0]
    assert stored != "hunter22"
    assert stored.startswith("$2b$")

# AUTHENTICATION IS REQUIRED

def test_protected_route_requires_token(client):
    assert client.get("/me/sessions").status_code == 401

def test_protected_route_rejects_garbage_token(client):
    res = client.get("/me/sessions", headers={"Authorization": "Bearer nonsense"})
    assert res.status_code == 401

def test_me_returns_the_token_holder(client, make_user):
    user = make_user("sherman")
    res = client.get("/me", headers=user["auth"])
    assert res.status_code == 200
    assert res.json()["username"] == "sherman"

# SESSIONS

def test_create_session(client, make_user):
    user = make_user()
    res = client.post("/me/sessions", json={}, headers=user["auth"])
    assert res.status_code == 201
    assert res.json()["user_id"] == user["user_id"]

def test_only_one_active_session(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    res = client.post("/me/sessions", json={}, headers=user["auth"])
    assert res.status_code == 409

def test_two_users_may_each_have_an_active_session(client, make_user):
    a, b = make_user("sherman"), make_user("ast")
    assert client.post("/me/sessions", json={}, headers=a["auth"]).status_code == 201
    assert client.post("/me/sessions", json={}, headers=b["auth"]).status_code == 201

def test_end_session_then_start_another(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    assert client.post("/me/sessions/end", json={}, headers=user["auth"]).status_code == 200
    assert client.post("/me/sessions", json={}, headers=user["auth"]).status_code == 201

def test_end_session_without_active_session(client, make_user):
    user = make_user()
    res = client.post("/me/sessions/end", json={}, headers=user["auth"])
    assert res.status_code == 400

def test_active_session_is_scoped_to_the_caller(client, make_user):
    a, b = make_user("sherman"), make_user("ast")
    client.post("/me/sessions", json={}, headers=a["auth"])
    assert client.get("/me/sessions/active", headers=a["auth"]).status_code == 200
    # b has no session of their own and must not see a's
    assert client.get("/me/sessions/active", headers=b["auth"]).status_code == 404

# SETS

def test_add_sets(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    payload = {"sets": [
        {"exercise": "bench press", "weight": 225, "reps": 5},
        {"exercise": "bench press", "weight": 225, "reps": 5},
    ]}
    res = client.post("/me/sets", json=payload, headers=user["auth"])
    assert res.status_code == 201
    assert res.json()["sets_inserted"] == 2

def test_add_sets_without_session(client, make_user):
    user = make_user()
    payload = {"sets": [{"exercise": "bench press", "weight": 225, "reps": 5}]}
    res = client.post("/me/sets", json=payload, headers=user["auth"])
    assert res.status_code == 400

def test_mixed_exercise_batch(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    payload = {"sets": [
        {"exercise": "bench press", "weight": 225, "reps": 5},
        {"exercise": "squat", "weight": 315, "reps": 5},
    ]}
    res = client.post("/me/sets", json=payload, headers=user["auth"])
    assert res.status_code == 400

def test_set_index_is_server_assigned_and_continues_across_requests(client, make_user):
    user = make_user()
    session = client.post("/me/sessions", json={}, headers=user["auth"]).json()
    body = {"sets": [{"exercise": "bench press", "weight": 225, "reps": 5}]}
    client.post("/me/sets", json=body, headers=user["auth"])
    client.post("/me/sets", json=body, headers=user["auth"])

    sets = client.get(f"/sessions/{session['session_id']}/sets", headers=user["auth"]).json()
    assert [s["set_index"] for s in sets] == [1, 2]

def test_exercise_names_are_normalized(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    client.post("/me/sets", headers=user["auth"],
                json={"sets": [{"exercise": "  Bench   Press ", "weight": 225, "reps": 5}]})
    assert client.get("/me/exercises", headers=user["auth"]).json() == ["bench press"]

def test_sets_for_exercise_returns_only_that_exercise(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    client.post("/me/sets", headers=user["auth"],
                json={"sets": [{"exercise": "bench press", "weight": 225, "reps": 5}]})
    client.post("/me/sets", headers=user["auth"],
                json={"sets": [{"exercise": "squat", "weight": 315, "reps": 3}]})

    res = client.get("/me/sets", params={"exercise": "bench press"}, headers=user["auth"])
    assert [s["weight"] for s in res.json()] == [225]

def test_cannot_read_another_users_session_sets(client, make_user):
    a, b = make_user("sherman"), make_user("ast")
    session = client.post("/me/sessions", json={}, headers=a["auth"]).json()
    client.post("/me/sets", headers=a["auth"],
                json={"sets": [{"exercise": "bench press", "weight": 225, "reps": 5}]})

    res = client.get(f"/sessions/{session['session_id']}/sets", headers=b["auth"])
    assert res.status_code == 403

def test_reading_a_missing_session_is_404(client, make_user):
    user = make_user()
    assert client.get("/sessions/9999/sets", headers=user["auth"]).status_code == 404

def test_negative_weight_is_rejected(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    res = client.post("/me/sets", headers=user["auth"],
                      json={"sets": [{"exercise": "bench press", "weight": -5, "reps": 5}]})
    assert res.status_code == 422

def test_zero_reps_is_rejected(client, make_user):
    user = make_user()
    client.post("/me/sessions", json={}, headers=user["auth"])
    res = client.post("/me/sets", headers=user["auth"],
                      json={"sets": [{"exercise": "bench press", "weight": 225, "reps": 0}]})
    assert res.status_code == 422
