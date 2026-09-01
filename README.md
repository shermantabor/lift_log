# lift_log

lift_log is a workout logging service built in Python, with a REST API backend and a single-page frontend.
It tracks training sessions and sets, with relational persistence, explicit business rules, token authentication, and a social layer for comparing lifts with friends.

The project is designed to
(1) help users progress in their lifting and
(2) demonstrate backend fundamentals: API design, data modeling, service-layer logic, authentication, and testability.

---

## Features

- REST API built with FastAPI
- Request validation using Pydantic
- Relational persistence with PostgreSQL
- **JWT bearer authentication** — every protected route resolves the caller from their token
- Password hashing with bcrypt (per-password salt)
- Social layer: friend requests, accept/decline, and friends-only access to lift data
- Explicit business rules enforced in the service layer:
  - One active session per user
  - Server-assigned ordering of sets per exercise
  - Only the addressee may accept a friend request; only the requester may cancel it
- Batch insertion of multiple sets in a single request
- Database integrity constraints (foreign keys, CHECKs, partial and expression unique indexes)
- Automated tests with pytest

---

## Architecture

```
Browser (frontend/index.html)  /  Swagger  /  curl
  ↓  Authorization: Bearer <token>
FastAPI Routes
  - HTTP handling
  - Request validation
  - Identity resolution (Depends(current_user_id))
  ↓  user_id
Service Layer
  - Business rules
  - Authorization rules (ownership, friendship)
  - Error translation
  ↓
Repository Layer
  - SQL queries only
  ↓
PostgreSQL
```

The service layer is intentionally independent of FastAPI so that business logic is reusable across interfaces (API, CLI, tests).

---

## Authentication

### How it works

Authentication is **stateless JWT bearer tokens**. There is no server-side session store.

1. A client calls `POST /users` (register) or `POST /login` with a username and password.
2. The server verifies the password against its bcrypt hash and returns a signed JWT.
3. The client sends that token on every subsequent request as `Authorization: Bearer <token>`.
4. Protected routes depend on `current_user_id`, which verifies the signature and returns the caller's `user_id`.

The token payload is minimal:

```json
{ "sub": "<user_id>", "iat": <issued at>, "exp": <issued at + 7 days> }
```

### The core rule: identity comes from the token, never the URL

This is the property that makes the API safe to expose. Routes do **not** accept a user id as input:

```python
@router.get("/me/sessions")
def read_sessions(user_id: int = Depends(current_user_id)):
    return get_sessions_for_user(user_id)
```

Because `user_id` is derived from a signed token, a caller cannot act as another user by editing a URL. Every route that reads or writes personal data lives under `/me/`.

Two routes take an id for a *different* user, and both authorize explicitly before returning anything:

- `GET /me/friends/{friend_id}/exercises` and `.../sets` — the service layer calls `db_are_friends` first and raises `403` unless an accepted friendship exists.
- `GET /sessions/{session_id}/sets` — session ids are sequential and guessable, so the service confirms the caller owns the session before returning its sets.

### Configuration

The signing secret is read from the environment at import time:

| Variable | Required | Purpose |
|---|---|---|
| `JWT_SECRET` | yes | HMAC key used to sign and verify tokens |
| `DATABASE_URL` | yes | PostgreSQL connection string |

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
export JWT_SECRET=<the value it printed>
```

**The app refuses to start if `JWT_SECRET` is unset.** This is deliberate — falling back to a hardcoded default would mean anyone who reads the source could mint a valid token for any account. Set it as an environment variable in your host's dashboard; never commit it.

Changing `JWT_SECRET` invalidates every outstanding token, which is also how you force a global logout.

### Token lifetime

Tokens are valid for **7 days** (`TOKEN_TTL` in [src/api/auth.py](src/api/auth.py)), after which the API returns `401` and the frontend returns the user to the login screen.

There is no refresh-token flow. For an app of this size it would add moving parts and failure modes without meaningfully improving security; re-logging in once a week is an acceptable trade.

### Frontend integration

The browser stores the token in `localStorage` and attaches it through a single wrapper, `apiFetch` (in [frontend/index.html](frontend/index.html)), so no call site handles auth by hand:

```js
const res = await apiFetch('/me/sessions', { method: 'POST', body: JSON.stringify({}) });
```

`apiFetch` attaches the `Authorization` header and, on any `401`, clears client state and reopens the login overlay. The `expiry` value kept alongside the token is only a local shortcut to skip a doomed request — the server's `exp` claim is what actually enforces expiry.

### Cross-site scripting

Because the token lives in `localStorage`, any script running on the page can read it. Values authored by users — usernames, exercise names — are therefore escaped with `esc()` before reaching `innerHTML`.

This matters specifically because of the social layer: a friend's username and exercise names render in *your* browser, so an unescaped `<img src=x onerror=...>` in someone else's data would execute with your token in scope. Use `textContent`, or wrap the value in `esc()`, when adding any new render path.

### Threat model

Protected against:

- Acting as another user by changing a URL (identity comes from the signed token)
- Reading a non-friend's lift data (`403` from the friendship check)
- Reading another user's session by guessing a session id (ownership check)
- Forged, expired, unsigned (`alg=none`), and malformed tokens — all covered by [tests/test_auth.py](tests/test_auth.py)
- Password disclosure from a database leak (bcrypt with per-password salt)

Known gaps, acceptable at this scale but worth naming:

- **No token revocation.** Tokens are stateless, so a stolen token is valid until it expires. Rotating `JWT_SECRET` revokes all tokens at once.
- **No rate limiting on `/login`**, so the endpoint is open to online password guessing.
- **No password reset or email verification** — there is no email on file.
- **`localStorage` is XSS-readable.** Mitigated by escaping (above), not eliminated. httpOnly cookies would be stronger but require the API and frontend to share a domain.

---

## API Reference

Public — no token required:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/users` | Register; returns a token |
| `POST` | `/login` | Log in; returns a token |

Protected — require `Authorization: Bearer <token>`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/me` | Current user |
| `GET` | `/me/exercises` | Distinct exercises you have logged |
| `GET` | `/me/sets?exercise=` | All your sets for one exercise |
| `POST` | `/me/sets` | Log one or more sets to the active session |
| `GET` | `/me/sessions` | Your session history |
| `POST` | `/me/sessions` | Start a session |
| `GET` | `/me/sessions/active` | Your open session, if any |
| `POST` | `/me/sessions/end` | End the open session |
| `GET` | `/sessions/{session_id}/sets` | Sets in one of your sessions |
| `GET` | `/me/search?q=` | Find users by username, with friendship status |
| `GET` | `/me/friends` | Accepted friends |
| `DELETE` | `/me/friends/{friend_id}` | Unfriend |
| `GET` | `/me/friend-requests` | Incoming and outgoing pending requests |
| `POST` | `/me/friend-requests` | Send a request by username |
| `POST` | `/me/friend-requests/{friendship_id}/respond` | Accept or decline |
| `DELETE` | `/me/friend-requests/{friendship_id}` | Cancel a request you sent |
| `GET` | `/me/friends/{friend_id}/exercises` | A friend's exercises |
| `GET` | `/me/friends/{friend_id}/sets?exercise=` | A friend's sets for one exercise |

Status codes: `400` invalid input, `401` missing/invalid/expired token, `403` authenticated but not permitted, `404` not found, `409` conflicting state (duplicate username, second active session, duplicate friend request).

---

## Data Model

### Users
- user_id (primary key)
- username (unique)
- password_hash (bcrypt)
- created_at

### Sessions
- session_id (primary key)
- user_id (foreign key → users)
- session_name, performed_at, notes, ended_at

Constraint: only one active session per user, enforced by a partial unique index on `(user_id) WHERE ended_at IS NULL`.

### Sets
- set_id (primary key)
- session_id (foreign key → sessions)
- exercise, weight (CHECK ≥ 0), reps (CHECK > 0), set_index (CHECK > 0), is_1rm

Constraint: sets are uniquely ordered per `(session_id, exercise, set_index)`. The server assigns `set_index` to prevent client-side ordering conflicts.

### Friendships
- friendship_id (primary key)
- requester_id, addressee_id (foreign keys → users)
- status — `pending` or `accepted`
- created_at, responded_at

Constraints:
- `CHECK (requester_id <> addressee_id)` — no self-friending.
- A unique index on `(LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))` — one row per pair regardless of direction, so B cannot open a second request to A while A's request to B is pending.

Declining a request **deletes** the row rather than storing a `declined` status, which keeps the pair index clean and lets either side ask again later. The trade-off is that there is no block/ignore capability.

---

## Running the API

Install dependencies:

```bash
pip install -r requirements.txt
```

Set the environment:

```bash
export DATABASE_URL=postgresql://user:password@host/dbname
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
```

Start the server:

```bash
uvicorn src.api.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs — use the **Authorize** button to paste a token and the protected routes become callable.

Tables are created on startup by `db_init_db()`, so a fresh database needs no migration step.

---

## Example API Usage (curl)

Register (or log in) and capture the token:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "sherman", "password": "hunter22"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Start a session:

```bash
curl -X POST http://127.0.0.1:8000/me/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes": "push day"}'
```

Add multiple sets (batch insert):

```bash
curl -X POST http://127.0.0.1:8000/me/sets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sets": [
      {"exercise": "bench press", "weight": 225, "reps": 5, "is_1rm": false},
      {"exercise": "bench press", "weight": 225, "reps": 5, "is_1rm": false},
      {"exercise": "bench press", "weight": 235, "reps": 3, "is_1rm": false}
    ]
  }'
```

End the active session:

```bash
curl -X POST http://127.0.0.1:8000/me/sessions/end \
  -H "Authorization: Bearer $TOKEN"
```

Send a friend request:

```bash
curl -X POST http://127.0.0.1:8000/me/friend-requests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "ast"}'
```

Without a token, every protected route returns `401`:

```bash
curl -i http://127.0.0.1:8000/me/sessions     # HTTP/1.1 401 Unauthorized
```

---

## Testing

Tests run against a **real PostgreSQL database**, so the schema and every query are exercised as written rather than mocked.

One-time setup:

```bash
brew install postgresql@17
brew services start postgresql@17
createdb lift_log_test
```

Then, from the repository root:

```bash
pytest
```

No environment variables are needed — [conftest.py](conftest.py) points the app at `postgresql://localhost/lift_log_test` and supplies a throwaway `JWT_SECRET`. Override the target with `TEST_DATABASE_URL` if you want a different scratch database.

**Safety:** the suite `TRUNCATE`s every table between tests, so `conftest.py` refuses to start if the target host is anything but localhost. A stray `DATABASE_URL` pointing at the deployed database cannot wipe it.

| File | Covers | Needs a database |
|---|---|---|
| [tests/test_auth.py](tests/test_auth.py) | Token round trip, expiry, wrong signing key, `alg=none` downgrade, malformed and subject-less tokens | No |
| [tests/test_api.py](tests/test_api.py) | Registration, login, bcrypt storage, session rules, set ordering and normalization, per-user isolation | Yes |
| [tests/test_social.py](tests/test_social.py) | Friend request lifecycle, who may accept/cancel, search status, friends-only data access, and the DB constraints themselves | Yes |

The last group is worth noting: because the service layer checks conflicts before the database sees them, two tests go straight to the repository to confirm the pair unique index and the self-friendship `CHECK` would still hold under a race.

---

## Design Decisions

- **PostgreSQL** replaced SQLite for hosted deployment and concurrent access.
- **Identity from the token, not the URL.** The single most important authorization property in the codebase; it makes an entire class of bug impossible rather than something each route must remember to check.
- **JWT over server-side sessions.** Stateless verification suits a separate frontend and API, needs no session store, and keeps the deployment to one process and one database.
- **Fail fast on a missing `JWT_SECRET`** rather than defaulting, so a misconfigured deploy is loud instead of silently insecure.
- **Authorization lives in the service layer**, alongside business rules, so it applies no matter which interface calls in.
- Database constraints act as a final line of defense against invalid data.
- Server-controlled set ordering avoids client-side race conditions.

---

## Future Improvements

- Rate-limit `/login` to blunt online password guessing
- Add CI (GitHub Actions) to run tests on every commit
- Normalize exercises into a dedicated table
- Add pagination for large session histories
- Optional containerization with Docker
