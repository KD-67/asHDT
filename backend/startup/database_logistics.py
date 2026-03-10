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
        # Table 3: Zone boundaries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS zone_references (
                id                       INTEGER PRIMARY KEY,
                module_id                TEXT NOT NULL,
                marker_id                TEXT NOT NULL,
                sex                      TEXT,
                age                      INTEGER,
                healthy_min              REAL NOT NULL,
                healthy_max              REAL NOT NULL,
                vulnerability_margin     REAL NOT NULL,
                UNIQUE(module_id, marker_id, sex, age)
            )
        """)
        # Table 4: Module catalog
        conn.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                module_id    TEXT PRIMARY KEY,
                module_name  TEXT,
                description  TEXT,
                format       TEXT
            )
        """)
        # Table 5: Marker catalog
        conn.execute("""
            CREATE TABLE IF NOT EXISTS markers (
                id               INTEGER PRIMARY KEY,
                module_id        TEXT NOT NULL,
                marker_id        TEXT NOT NULL,
                marker_name      TEXT,
                description      TEXT,
                unit             TEXT,
                volatility_class TEXT,
                UNIQUE(module_id, marker_id)
            )
        """)
        # Runtime migrations for existing DBs
        try:
            conn.execute("ALTER TABLE modules ADD COLUMN module_name TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE markers ADD COLUMN marker_name TEXT")
        except Exception:
            pass
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
                INSERT INTO subjects (subject_id, first_name, last_name, sex, dob, email, phone, notes, created_at)
                VALUES (:subject_id, :first_name, :last_name, :sex, :dob, :email, :phone, :notes, :created_at)
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
                    "created_at": p.get("created_at", ""),
                },
            )
        conn.commit()

# Reads module_list.json and upserts every module and marker into the modules/markers tables
def sync_modules(db_path: str, modules_path: str):
    if not os.path.isfile(modules_path):
        return
    with open(modules_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    with get_connection(db_path) as conn:
        for mod in data.get("modules", []):
            conn.execute(
                "INSERT INTO modules (module_id, module_name, description, format) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(module_id) DO UPDATE SET module_name=excluded.module_name, description=excluded.description, format=excluded.format",
                (mod["module_id"], mod.get("module_name"), mod.get("description"), mod.get("format")),
            )
            for mk in mod.get("markers", []):
                conn.execute(
                    "INSERT INTO markers (module_id, marker_id, marker_name, description, unit, volatility_class) "
                    "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(module_id, marker_id) DO UPDATE SET "
                    "marker_name=excluded.marker_name, description=excluded.description, unit=excluded.unit, volatility_class=excluded.volatility_class",
                    (mod["module_id"], mk["marker_id"], mk.get("marker_name"), mk.get("description"), mk.get("unit"), mk.get("volatility_class")),
                )
        conn.commit()

def _datapoint_table(subject_id: str, module_id: str, marker_id: str) -> str:
    """Returns the DB table name for a given (subject, module, marker) triple."""
    return f"{subject_id}__{module_id}__{marker_id}"

def _ensure_datapoint_table(conn, table_name: str):
    """Creates the per-subject-marker table if it does not yet exist."""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            id           INTEGER PRIMARY KEY,
            measured_at  TEXT NOT NULL UNIQUE,
            value        REAL NOT NULL,
            unit         TEXT,
            data_quality TEXT,
            created_at   TEXT NOT NULL
        )
    """)

# Walks every index.json under rawdata_root and upserts all datapoints into per-subject-marker tables
def sync_datapoints(db_path: str, rawdata_root: str):
    if not os.path.isdir(rawdata_root):
        return
    with get_connection(db_path) as conn:
        for subject_id in os.listdir(rawdata_root):
            subject_dir = os.path.join(rawdata_root, subject_id)
            if not os.path.isdir(subject_dir):
                continue
            for module_id in os.listdir(subject_dir):
                module_dir = os.path.join(subject_dir, module_id)
                if not os.path.isdir(module_dir):
                    continue
                for marker_id in os.listdir(module_dir):
                    marker_dir = os.path.join(module_dir, marker_id)
                    index_path = os.path.join(marker_dir, "index.json")
                    if not os.path.isfile(index_path):
                        continue
                    with open(index_path, "r", encoding="utf-8") as f:
                        index = json.load(f)
                    table = _datapoint_table(subject_id, module_id, marker_id)
                    _ensure_datapoint_table(conn, table)
                    for entry in index.get("entries", []):
                        file_path = os.path.join(marker_dir, entry["file"])
                        if not os.path.isfile(file_path):
                            continue
                        with open(file_path, "r", encoding="utf-8") as f:
                            dp = json.load(f)
                        conn.execute(
                            f'INSERT INTO "{table}" (measured_at, value, unit, data_quality, created_at) '
                            f'VALUES (?, ?, ?, ?, ?) ON CONFLICT(measured_at) DO UPDATE SET '
                            f'value=excluded.value, unit=excluded.unit, data_quality=excluded.data_quality, created_at=excluded.created_at',
                            (dp["measured_at"], dp["value"], dp.get("unit"), dp.get("data_quality"), dp.get("created_at", "")),
                        )
        conn.commit()

# Scans marker reference range jsons and upserts into zone_references table on startup
def sync_zone_references(db_path: str, references_root: str):
    if not os.path.isdir(references_root):
        return
    with get_connection(db_path) as conn:
        for module_id in os.listdir(references_root):
            module_dir = os.path.join(references_root, module_id)
            if not os.path.isdir(module_dir):
                continue
            for filename in os.listdir(module_dir):
                if not filename.endswith(".json"):
                    continue
                marker_id = filename[:-5]
                with open(os.path.join(module_dir, filename), "r") as f:
                    data = json.load(f)
                    if "generic" in data:
                        g = data["generic"]
                        # Delete+insert for generic row (NULL sex/age can't use ON CONFLICT)
                        conn.execute(
                            "DELETE FROM zone_references WHERE module_id=? AND marker_id=? AND sex IS NULL AND age IS NULL",
                            (module_id, marker_id),
                        )
                        conn.execute(
                            "INSERT INTO zone_references (module_id, marker_id, sex, age, healthy_min, healthy_max, vulnerability_margin) "
                            "VALUES (?, ?, NULL, NULL, ?, ?, ?)",
                            (module_id, marker_id, g["healthy_min"], g["healthy_max"], g["vulnerability_margin"]),
                        )
                    # Upsert per-sex per-age rows
                    for sex, sex_data in data.get("by_sex", {}).items():
                        for age_str, vals in sex_data.get("by_age", {}).items():
                            conn.execute(
                                """
                                INSERT INTO zone_references (module_id, marker_id, sex, age, healthy_min,
                                  healthy_max, vulnerability_margin)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(module_id, marker_id, sex, age) DO UPDATE SET
                                    healthy_min          = excluded.healthy_min,
                                    healthy_max          = excluded.healthy_max,
                                    vulnerability_margin = excluded.vulnerability_margin
                                """,
                                (module_id, marker_id, sex, int(age_str), vals["healthy_min"],
                                 vals["healthy_max"], vals["vulnerability_margin"]),
                            )
        conn.commit()