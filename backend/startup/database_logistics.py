# Checks if the SQLite database exists and has all required tables. If yes - move on, if no - create it. 

import sqlite3
import os

def init_db (db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True) # safe to call even if dir already exists
    with get_connection(db_path) as conn: # connect to (or create) db file
       # Table 1: Subjects
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id          INTEGER PRIMARY KEY,
                subject_id  TEXT,
                last_name   TEXT,
                first_name  TEXT,
                sex         TEXT,
                dob         TEXT,
                email       TEXT,
                phone       TEXT,
                notes       TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Table 2: Reports
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timegraph_reports (
                report_id                TEXT PRIMARY KEY,
                subject_id               TEXT NOT NULL,
                marker_id                TEXT NOT NULL,
                module_id                TEXT NOT NULL,
                requested_at             TEXT NOT NULL,
                timeframe_from           TEXT NOT NULL,
                timeframe_to             TEXT NOT NULL,
                polynomial_degree        INTEGER NOT NULL,
                healthy_min              REAL NOT NULL,
                healthy_max              REAL NOT NULL,
                vulnerability_margin     REAL NOT NULL
            )
        """)

# Opens connection to the SQLite db defined at db_path. sqlite.row makes columns accessible by name, not just by index position
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
