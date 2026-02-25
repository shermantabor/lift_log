# lift_log

lift_log is a backend workout logging service built in Python.
It exposes a REST API for tracking training sessions and workout sets, with relational persistence, explicit business rules, and automated tests.

The project is designed to
(1) help users progress in their lifting and
(2) demonstrate backend fundamentals: API design, data modeling, service-layer logic, and testability.

---

## Features

- REST API built with FastAPI
- Request validation using Pydantic
- Relational persistence with SQLite
- Explicit business rules enforced in the service layer:
  - One active session per user
  - Server-assigned ordering of sets per exercise
- Batch insertion of multiple sets in a single request
- Database integrity constraints (foreign keys, CHECKs, partial unique index)
- Automated tests with pytest and FastAPI TestClient
- Isolated test databases (no shared state between tests)

---

## Architecture

Client (Swagger / Postman / CLI)
  ↓
FastAPI Routes
  - HTTP handling
  - Request validation
  ↓
Service Layer
  - Business rules
  - State validation
  - Error translation
  ↓
Repository Layer
  - SQL queries only
  ↓
SQLite Database
  - Foreign keys
  - CHECK constraints
  - Partial unique index

The service layer is intentionally independent of FastAPI so that business logic is reusable across interfaces (API, CLI, tests).

---

## Data Model

### Users
- user_id (primary key)
- username (unique)
- created_at

### Sessions
- session_id (primary key)
- user_id (foreign key → users)
- performed_at
- notes
- ended_at

Constraint:
Only one active session per user is allowed.
This is enforced via service-layer checks and a partial unique index on (user_id) where ended_at IS NULL.

### Sets
- set_id (primary key)
- session_id (foreign key → sessions)
- exercise
- weight (CHECK ≥ 0)
- reps (CHECK > 0)
- set_index (CHECK > 0)
- is_1rm (boolean)

Constraint:
Sets are uniquely ordered per (session_id, exercise, set_index).

The server assigns set_index automatically to prevent client-side ordering conflicts.

---

## Running the API

Install dependencies:
pip install -r requirements.txt

Start the server:
uvicorn src.api.main:app --reload

Swagger UI:
http://127.0.0.1:8000/docs

---

## Example API Usage (curl)

Create a user:
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "sherman"
  }'

Start a session:
curl -X POST http://127.0.0.1:8000/users/1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "push day"
  }'

Add multiple sets (batch insert):
curl -X POST http://127.0.0.1:8000/users/1/sets \
  -H "Content-Type: application/json" \
  -d '{
    "sets": [
      {
        "exercise": "bench press",
        "weight": 225,
        "reps": 5,
        "is_1rm": false
      },
      {
        "exercise": "bench press",
        "weight": 225,
        "reps": 5,
        "is_1rm": false
      },
      {
        "exercise": "bench press",
        "weight": 235,
        "reps": 3,
        "is_1rm": false
      }
    ]
  }'

End the active session:
curl -X POST http://127.0.0.1:8000/users/1/sessions/end

---

## Testing

Tests are written using pytest and FastAPI’s TestClient.

Each test runs against an isolated temporary SQLite database:
- the schema is initialized per test
- no test shares state with another
- production data is never touched

Run tests from the repository root:
pytest

---

## Design Decisions

- SQLite was chosen for simplicity and strong relational guarantees.
- Service-layer business rules ensure correct behavior before hitting the database.
- Database constraints act as a final line of defense against invalid data.
- Server-controlled set ordering avoids client-side race conditions and conflicts.
- Authentication is intentionally omitted to keep the project focused on backend fundamentals.

---

## Future Improvements

- Add read-only endpoints for session summaries and volume statistics
- Normalize exercises into a dedicated table
- Add pagination for large session histories
- Add CI (GitHub Actions) to run tests on every commit
- Optional containerization with Docker