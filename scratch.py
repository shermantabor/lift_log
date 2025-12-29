'''
    poking around the db
'''

import sqlite3
from pathlib import Path
from main import DB_PATH
from main import DATA_DIR

# ensure data directory exists
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "lift_log.db"

def what_tables_do_we_have():
    # ensure we get an error if DB DNE or if we run from wrong directory
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    cursor = con.cursor()

    # enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # query sqlite to see tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    cursor.execute("PRAGMA table_info(sessions)")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

def main():
    what_tables_do_we_have()

if __name__ == '__main__':
    main()

