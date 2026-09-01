"""
Friend request lifecycle and friends-only access to lift data.
"""

import pytest

@pytest.fixture
def pair(make_user):
    '''two registered users: the requester and the addressee'''
    return make_user("sherman"), make_user("ast")

def send_request(client, sender, to_username):
    return client.post("/me/friend-requests",
                       json={"username": to_username}, headers=sender["auth"])

def log_set(client, user, exercise="bench press", weight=225, reps=5):
    client.post("/me/sessions", json={}, headers=user["auth"])
    return client.post("/me/sets", headers=user["auth"],
                       json={"sets": [{"exercise": exercise, "weight": weight, "reps": reps}]})

# SENDING

def test_send_friend_request(client, pair):
    a, b = pair
    res = send_request(client, a, "ast")
    assert res.status_code == 201
    assert res.json()["status"] == "pending"

def test_request_appears_for_both_sides(client, pair):
    a, b = pair
    send_request(client, a, "ast")

    outgoing = client.get("/me/friend-requests", headers=a["auth"]).json()
    assert [r["username"] for r in outgoing["outgoing"]] == ["ast"]
    assert outgoing["incoming"] == []

    incoming = client.get("/me/friend-requests", headers=b["auth"]).json()
    assert [r["username"] for r in incoming["incoming"]] == ["sherman"]
    assert incoming["outgoing"] == []

def test_cannot_friend_yourself(client, pair):
    a, _ = pair
    assert send_request(client, a, "sherman").status_code == 400

def test_request_to_unknown_user(client, pair):
    a, _ = pair
    assert send_request(client, a, "ghost").status_code == 404

def test_duplicate_request_is_rejected(client, pair):
    a, _ = pair
    send_request(client, a, "ast")
    assert send_request(client, a, "ast").status_code == 409

def test_reverse_request_is_rejected_while_one_is_pending(client, pair):
    '''B asking A, while A->B is open, is caught by the service with a useful message'''
    a, b = pair
    send_request(client, a, "ast")
    res = send_request(client, b, "sherman")
    assert res.status_code == 409
    assert "accept it instead" in res.json()["detail"]

# DATABASE CONSTRAINTS
#
# The service layer checks these first, so these tests go straight to the
# repository to confirm the schema itself would hold under a race.

def test_pair_index_blocks_a_reverse_duplicate_row(client, pair):
    import psycopg2
    from src.repository.db import get_conn, db_create_friend_request

    a, b = pair
    with get_conn() as conn:
        db_create_friend_request(conn, a["user_id"], b["user_id"], "2026-01-01T00:00:00")

    with pytest.raises(psycopg2.errors.UniqueViolation):
        with get_conn() as conn:
            # same pair, opposite direction
            db_create_friend_request(conn, b["user_id"], a["user_id"], "2026-01-01T00:00:01")

def test_check_constraint_blocks_self_friendship(client, pair):
    import psycopg2
    from src.repository.db import get_conn, db_create_friend_request

    a, _ = pair
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_conn() as conn:
            db_create_friend_request(conn, a["user_id"], a["user_id"], "2026-01-01T00:00:00")

# ACCEPTING & DECLINING

def test_accept_makes_both_users_friends(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    assert client.post(f"/me/friend-requests/{fid}/respond",
                       json={"accept": True}, headers=b["auth"]).status_code == 200

    assert [f["username"] for f in client.get("/me/friends", headers=a["auth"]).json()] == ["ast"]
    assert [f["username"] for f in client.get("/me/friends", headers=b["auth"]).json()] == ["sherman"]

def test_accepting_clears_the_pending_lists(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])

    assert client.get("/me/friend-requests", headers=a["auth"]).json()["outgoing"] == []
    assert client.get("/me/friend-requests", headers=b["auth"]).json()["incoming"] == []

def test_requester_cannot_accept_their_own_request(client, pair):
    a, _ = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    res = client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=a["auth"])
    assert res.status_code == 403

def test_third_party_cannot_accept_a_request(client, pair, make_user):
    a, _ = pair
    c = make_user("intruder")
    fid = send_request(client, a, "ast").json()["friendship_id"]
    res = client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=c["auth"])
    assert res.status_code == 403

def test_decline_removes_the_request(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    assert client.post(f"/me/friend-requests/{fid}/respond",
                       json={"accept": False}, headers=b["auth"]).status_code == 200

    assert client.get("/me/friends", headers=a["auth"]).json() == []
    assert client.get("/me/friend-requests", headers=a["auth"]).json()["outgoing"] == []

def test_can_request_again_after_being_declined(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": False}, headers=b["auth"])
    assert send_request(client, a, "ast").status_code == 201

def test_cannot_accept_an_already_accepted_request(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])
    res = client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])
    assert res.status_code == 409

def test_request_when_already_friends_is_rejected(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])
    assert send_request(client, a, "ast").status_code == 409

# CANCELLING & UNFRIENDING

def test_requester_can_cancel(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    assert client.delete(f"/me/friend-requests/{fid}", headers=a["auth"]).status_code == 200
    assert client.get("/me/friend-requests", headers=b["auth"]).json()["incoming"] == []

def test_addressee_cannot_cancel(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    assert client.delete(f"/me/friend-requests/{fid}", headers=b["auth"]).status_code == 403

def test_unfriend_is_mutual(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])

    assert client.delete(f"/me/friends/{b['user_id']}", headers=a["auth"]).status_code == 200
    assert client.get("/me/friends", headers=a["auth"]).json() == []
    assert client.get("/me/friends", headers=b["auth"]).json() == []

def test_unfriend_a_non_friend(client, pair):
    a, b = pair
    assert client.delete(f"/me/friends/{b['user_id']}", headers=a["auth"]).status_code == 404

# SEARCH

def test_search_reports_relationship_status(client, pair, make_user):
    a, b = pair
    make_user("astrid")

    results = {r["username"]: r["status"]
               for r in client.get("/me/search", params={"q": "ast"}, headers=a["auth"]).json()}
    assert results == {"ast": "none", "astrid": "none"}

    send_request(client, a, "ast")
    after = {r["username"]: r["status"]
             for r in client.get("/me/search", params={"q": "ast"}, headers=a["auth"]).json()}
    assert after["ast"] == "request_sent"

    # and from the other side of the same request
    theirs = client.get("/me/search", params={"q": "sherman"}, headers=b["auth"]).json()
    assert theirs[0]["status"] == "request_received"

def test_search_status_after_accepting(client, pair):
    a, b = pair
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])

    res = client.get("/me/search", params={"q": "ast"}, headers=a["auth"]).json()
    assert res[0]["status"] == "friends"

def test_search_excludes_self(client, pair):
    a, _ = pair
    res = client.get("/me/search", params={"q": "sherman"}, headers=a["auth"]).json()
    assert res == []

def test_search_is_case_insensitive(client, pair):
    a, _ = pair
    res = client.get("/me/search", params={"q": "AST"}, headers=a["auth"]).json()
    assert [r["username"] for r in res] == ["ast"]

# FRIENDS-ONLY ACCESS TO LIFT DATA

def test_non_friend_cannot_read_lifts(client, pair):
    a, b = pair
    log_set(client, b)
    assert client.get(f"/me/friends/{b['user_id']}/sets",
                      params={"exercise": "bench press"}, headers=a["auth"]).status_code == 403
    assert client.get(f"/me/friends/{b['user_id']}/exercises",
                      headers=a["auth"]).status_code == 403

def test_pending_request_does_not_grant_access(client, pair):
    a, b = pair
    log_set(client, b)
    send_request(client, a, "ast")
    assert client.get(f"/me/friends/{b['user_id']}/exercises",
                      headers=a["auth"]).status_code == 403

def test_friend_can_read_lifts(client, pair):
    a, b = pair
    log_set(client, b, weight=315, reps=3)
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])

    assert client.get(f"/me/friends/{b['user_id']}/exercises",
                      headers=a["auth"]).json() == ["bench press"]

    sets = client.get(f"/me/friends/{b['user_id']}/sets",
                      params={"exercise": "bench press"}, headers=a["auth"]).json()
    assert [(s["weight"], s["reps"]) for s in sets] == [(315, 3)]

def test_unfriending_revokes_access(client, pair):
    a, b = pair
    log_set(client, b)
    fid = send_request(client, a, "ast").json()["friendship_id"]
    client.post(f"/me/friend-requests/{fid}/respond", json={"accept": True}, headers=b["auth"])
    client.delete(f"/me/friends/{b['user_id']}", headers=a["auth"])

    assert client.get(f"/me/friends/{b['user_id']}/exercises",
                      headers=a["auth"]).status_code == 403

def test_friend_endpoints_require_a_token(client, pair):
    _, b = pair
    assert client.get(f"/me/friends/{b['user_id']}/exercises").status_code == 401
