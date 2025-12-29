'''
test suite for lift_log
'''

import unittest
import sqlite3
from datetime import datetime

# import functions to test
from src.main import parse_entry_line, parse_set_token, insert_sets, get_next_set_index

def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("""
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
    """)

    conn.execute("""
        CREATE TABLE sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            performed_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    conn.execute("""
        CREATE TABLE sets (
            set_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise TEXT NOT NULL,
            weight REAL NOT NULL,
            reps INTEGER NOT NULL,
            set_index INTEGER NOT NULL,
            is_1rm INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
    """)
    conn.commit()

class TestParsing(unittest.TestCase):
    def test_parse_entry_line_ok(self):
        exercise, tokens = parse_entry_line("Bench press: 135x5, 155x3")
        self.assertEqual(exercise, "bench press")
        self.assertEqual(tokens, ["135x5", "155x3"])

    def test_parse_entry_line_missing_colon(self):
        with self.assertRaises(ValueError):
            parse_entry_line("Bench press 135x5")

    def test_parse_set_token_ok(self):
        w, r = parse_set_token(" 135 x 5 ")
        self.assertEqual(w, 135.0)
        self.assertEqual(r, 5)

    def test_parse_set_token_bad(self):
        with self.assertRaises(ValueError):
            parse_set_token("135x")

class TestDBIntegration(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_schema(self.conn)

        # create a user and a session
        created_at = datetime.now().isoformat(timespec="seconds")
        self.conn.execute("INSERT INTO users (username, created_at) VALUES (?, ?);", ("alex", created_at))
        self.user_id = self.conn.execute("SELECT user_id FROM users WHERE username = ?;", ("alex",)).fetchone()[0]

        performed_at = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO sessions (user_id, performed_at, notes) VALUES (?, ?, ?);",
            (self.user_id, performed_at, None)
        )
        self.session_id = self.conn.execute("SELECT MAX(session_id) FROM sessions;").fetchone()[0]
        self.conn.commit()

    def tearDown(self):
        if hasattr(self, "conn") and self.conn is not None:
            self.conn.close()

    def test_sets_attach_to_user_via_session(self):
        rows = [
            (135.0, 5, 0),
            (155.0, 3, 0),
        ]
        insert_sets(self.conn, self.session_id, "bench press", rows)
        self.conn.commit()

        result = self.conn.execute("""
            SELECT u.username, st.exercise, st.weight, st.reps
            FROM sets st
            JOIN sessions s ON st.session_id = s.session_id
            JOIN users u ON s.user_id = u.user_id
            WHERE st.session_id = ?
            ORDER BY st.set_index;
        """, (self.session_id,)).fetchall()

        self.assertEqual(result[0][0], "alex")
        self.assertEqual(result[0][1], "bench press")
        self.assertAlmostEqual(result[0][2], 135.0)
        self.assertEqual(result[0][3], 5)

    def test_set_index_continues(self):
        insert_sets(self.conn, self.session_id, "bench press", [(135.0, 5, 0), (155.0, 3, 0)])
        self.conn.commit()

        insert_sets(self.conn, self.session_id, "bench press", [(175.0, 1, 1)])
        self.conn.commit()

        indices = self.conn.execute("""
            SELECT set_index FROM sets
            WHERE session_id = ? AND exercise = ?
            ORDER BY set_index;
        """, (self.session_id, "bench press")).fetchall()

        self.assertEqual([i[0] for i in indices], [1, 2, 3])

if __name__=="__main__":
    unittest.main()