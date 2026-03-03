# Checks if the SQLite database exists and has all required tables. If yes - move on, if no - create it. 

import sqlite3
import os
import json

def init_db (db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True) # safe to call even if dir already exists
    with get_connection(db_path) as conn: # connect to (or create) db file
       # Table 1: Subjects
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id          INTEGER PRIMARY KEY,
                subject_id  TEXT UNIQUE,
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
                module_id                TEXT NOT NULL,
                marker_id                TEXT NOT NULL,
                requested_at             TEXT NOT NULL,
                timeframe_from           TEXT NOT NULL,
                timeframe_to             TEXT NOT NULL,
                polynomial_degree        INTEGER NOT NULL,
                healthy_min              REAL NOT NULL,
                healthy_max              REAL NOT NULL,
                vulnerability_margin     REAL NOT NULL
            )
        """)
        conn.commit()

# Opens connection to the SQLite db defined at db_path. sqlite.row makes columns accessible by name, not just by index position
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Scans all subject directories and upserts individual profile data into the subjects table of asHDT.db
def sync_subjects(db_path: str, rawdata_root: str):
    with get_connection(db_path) as conn:
        for subject_dir in os.listdir(rawdata_root):
            profile_path = os.path.join(rawdata_root, subject_dir, "profile.json")
            if not os.path.isfile(profile_path):
                continue
            with open(profile_path, "r") as f:
                p = json.load(f)
            conn.execute(
                """
                INSERT INTO subjects (subject_id, first_name, last_name, sex, dob, email, phone, notes)
                VALUES (:subject_id, :first_name, :last_name, :sex, :dob, :email, :phone, :notes)
                ON CONFLICT(subject_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    last_name  = excluded.last_name,
                    sex        = excluded.sex,
                    dob        = excluded.dob,
                    email      = excluded.email,
                    phone      = excluded.phone,
                    notes      = excluded.notes
                """,
                {
                    "subject_id": p.get("subject_id"),
                    "first_name": p.get("first_name"),
                    "last_name":  p.get("last_name"),
                    "sex":        p.get("sex"),
                    "dob":        p.get("dob"),
                    "email":      p.get("email"),
                    "phone":      p.get("phone"),
                    "notes":      p.get("notes"),
                },
            )
        conn.commit()