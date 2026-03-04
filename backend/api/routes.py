# Defines the endpoints and pydantic request models that the application (app = fastAPI() from main.py) uses.
# The current endpoints are:
# 1. GET modules
# 2. GET subjects
# 3. GET subject profile data
# 4. POST subjects (create)
# 5. PUT subjects (edit)
# 6. DELETE subjects
# 7. POST timegraph data

import os
import json
from datetime import datetime, timezone, date
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from backend.core.storage.data_reader import read_timeseries
from backend.startup.database_logistics import get_connection, _datapoint_table, _ensure_datapoint_table
from backend.core.analysis.trajectory_computer import compute_trajectory
from backend.core.output.report_generator import save_timegraph_report

router = APIRouter()

# Pydantic request models for taking in timegraph report data
class TimeframeModel(BaseModel):
    start_time: str
    end_time: str

class ZoneBoundariesModel(BaseModel):
    healthy_min: float
    healthy_max: float
    vulnerability_margin: float

class FittingModel(BaseModel):
    polynomial_degree: int

class TimegraphRequest(BaseModel):
    subject_id: str
    module_id: str
    marker_id: str
    timeframe: TimeframeModel
    zone_boundaries: ZoneBoundariesModel
    fitting: FittingModel

class SubjectProfile(BaseModel):
    first_name: str
    last_name: str
    sex: str
    dob: str
    email: str
    phone: str
    notes: str = ""

class ModuleCreate(BaseModel):
    module_id: str
    description: str
    format: str = "json"

class ModuleUpdate(BaseModel):
    description: str

class MarkerCreate(BaseModel):
    marker_id: str
    description: str
    unit: str
    volatility_class: str
    healthy_min: float
    healthy_max: float
    vulnerability_margin: float

class MarkerUpdate(BaseModel):
    description: str
    unit: str
    volatility_class: str
    healthy_min: float
    healthy_max: float
    vulnerability_margin: float

class DatapointCreate(BaseModel):
    measured_at: str
    value: float
    unit: str
    data_quality: str = "good"

# Functions
def _write_modules(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _save_index(index_path: str, data: dict):
    with open(index_path, "w", encoding ="utf-8") as f:
        json.dump(data, f, indent=2)


# Routes

# Return module list
@router.get("/modules")
def get_modules(request: Request):
    return request.app.state.modules

# Return subject directory list
@router.get("/subjects")
def get_subjects(request: Request):
    rawdata_root = request.app.state.rawdata_root
    if not os.path.isdir(rawdata_root):
        return []
    return [
        name for name in os.listdir(rawdata_root)
        if os.path.isdir(os.path.join(rawdata_root, name))
    ]

# Return profile data of specified subject
@router.get("/subjects/{subject_id}/profile")
async def get_subject_profile(subject_id: str, request: Request):
    with get_connection(request.app.state.db_path) as conn:
        row = conn.execute(
            "SELECT * FROM subjects WHERE subject_id = ?", (subject_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Subject profile not found")
    return dict(row)

# Return interpolated zone boundary suggestions for a given subject & marker
@router.get("/subjects/{subject_id}/zone-reference/{module_id}/{marker_id}")
def get_zone_references(subject_id: str, module_id:str, marker_id: str, request: Request):
    db_path = request.app.state.db_path
    with get_connection(db_path) as conn:
        subject = conn.execute(
            "SELECT sex, dob FROM subjects WHERE subject_id = ?", (subject_id,)
        ).fetchone()
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        sex = subject["sex"]
        dob = subject["dob"]
        # Calculate age in whole years
        age = None
        if dob:
            try:
                birth = date.fromisoformat(dob[:10])
                today = date.today()
                age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            except ValueError:
                pass
    # Query sex-specific rows ordered by age
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT age, healthy_min, healthy_max, vulnerability_margin FROM zone_references "
            "WHERE module_id = ? AND marker_id = ? AND sex = ? AND age IS NOT NULL ORDER BY age",
            (module_id, marker_id, sex),
        ).fetchall()
    note = None
    result = None
    if rows and age is not None:
        ages = [r["age"] for r in rows]
        if age <= ages[0]:
            r = rows[0]
            result = (r["healthy_min"], r["healthy_max"], r["vulnerability_margin"])
        elif age >= ages[-1]:
            r = rows[-1]
            result = (r["healthy_min"], r["healthy_max"], r["vulnerability_margin"])
        else:
            for i in range(len(rows) - 1):
                if ages[i] <= age <= ages[i + 1]:
                    lo, hi = rows[i], rows[i + 1]
                    t = (age - ages[i]) / (ages[i + 1] - ages[i])
                    result = (
                        lo["healthy_min"]          + t * (hi["healthy_min"]          - lo["healthy_min"]),
                        lo["healthy_max"]          + t * (hi["healthy_max"]          - lo["healthy_max"]),
                        lo["vulnerability_margin"] + t * (hi["vulnerability_margin"] -
lo["vulnerability_margin"]),
                    )
                    break
    # Fall back to generic if no sex-specific result
    if result is None:
        with get_connection(db_path) as conn:
            generic = conn.execute(
                "SELECT healthy_min, healthy_max, vulnerability_margin FROM zone_references "
                "WHERE module_id = ? AND marker_id = ? AND sex IS NULL AND age IS NULL",
                (module_id, marker_id),
            ).fetchone()
        if generic is None:
            raise HTTPException(status_code=404, detail="No reference data available for this marker")    
        result = (generic["healthy_min"], generic["healthy_max"], generic["vulnerability_margin"])        
        note = "No sex/age-specific reference data available for this marker; using generic values."      
    return {
        "healthy_min":          result[0],
        "healthy_max":          result[1],
        "vulnerability_margin": result[2],
        "note":                 note,
    }

# Create a new subject: auto-generate subject_id, create directory, write profile.json, insert into DB
@router.post("/subjects", status_code=201)
def post_subject(body: SubjectProfile, request: Request):
    rawdata_root = request.app.state.rawdata_root
    db_path = request.app.state.db_path
    existing = [
        name for name in os.listdir(rawdata_root)
        if os.path.isdir(os.path.join(rawdata_root, name))
    ] if os.path.isdir(rawdata_root) else []
    max_num = 0
    for name in existing:
        parts = name.split("_")
        if len(parts) == 2 and parts[0] == "subject" and parts[1].isdigit():
            max_num = max(max_num, int(parts[1]))
    subject_id = f"subject_{str(max_num + 1).zfill(3)}"
    subject_dir = os.path.join(rawdata_root, subject_id)
    os.makedirs(subject_dir, exist_ok=True)
    profile = {"subject_id": subject_id, **body.model_dump()}
    with open(os.path.join(subject_dir, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO subjects (subject_id, first_name, last_name, sex, dob, email, phone, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (subject_id, body.first_name, body.last_name, body.sex, body.dob, body.email, body.phone, body.notes),
        )
        conn.commit()
    return {"subject_id": subject_id}

# Edit an existing subject's profile: update profile.json and DB row
@router.put("/subjects/{subject_id}")
def put_subject(subject_id: str, body: SubjectProfile, request: Request):
    rawdata_root = request.app.state.rawdata_root
    db_path = request.app.state.db_path
    profile_path = os.path.join(rawdata_root, subject_id, "profile.json")
    if not os.path.isfile(profile_path):
        raise HTTPException(status_code=404, detail="Subject not found")
    profile = {"subject_id": subject_id, **body.model_dump()}
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE subjects SET first_name=?, last_name=?, sex=?, dob=?, email=?, phone=?, notes=? WHERE subject_id=?",
            (body.first_name, body.last_name, body.sex, body.dob, body.email, body.phone, body.notes, subject_id),
        )
        conn.commit()
    return {"subject_id": subject_id}

# Delete a subject: remove DB row and move directory to deleted_subjects/
@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: str, request: Request):
    import shutil
    rawdata_root = request.app.state.rawdata_root
    db_path = request.app.state.db_path
    subject_dir = os.path.join(rawdata_root, subject_id)
    if not os.path.isdir(subject_dir):
        raise HTTPException(status_code=404, detail="Subject not found")
    deleted_root = os.path.join(os.path.dirname(rawdata_root), "deleted_subjects")
    os.makedirs(deleted_root, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    shutil.move(subject_dir, os.path.join(deleted_root, f"{subject_id}_{timestamp}"))
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
        conn.commit()
    return {"subject_id": subject_id}

# Create a new module
@router.post("/modules", status_code=201)
def post_module(body: ModuleCreate, request: Request):
    path = request.app.state.modules_path
    modules = request.app.state.modules
    if any(m["module_id"] == body.module_id for m in modules["modules"]):
        raise HTTPException(status_code=409, detail="module_id already exists!")
    modules["modules"].append({
        "module_id": body.module_id,
        "description": body.description,
        "format": body.format,
        "markers": [],
    })
    _write_modules(path, modules)
    request.app.state.modules = modules
    with get_connection(request.app.state.db_path) as conn:
        conn.execute(
            "INSERT INTO modules (module_id, description, format) VALUES (?, ?, ?)",
            (body.module_id, body.description, body.format),
        )
        conn.commit()
    return {"module_id": body.module_id}

# Edit existing module
@router.put("/modules/{module_id}")
def put_module(module_id: str, body: ModuleUpdate, request: Request):
    path = request.app.state.modules_path
    modules = request.app.state.modules
    mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
    if mod is None:
        raise HTTPException(status_code=404, detail="Module not found")
    mod["description"] = body.description
    _write_modules(path, modules)
    request.app.state.modules = modules
    with get_connection(request.app.state.db_path) as conn:
        conn.execute(
            "UPDATE modules SET description=? WHERE module_id=?",
            (body.description, module_id),
        )
        conn.commit()
    return {"module_id": module_id}

# Delete existing module
@router.delete("/modules/{module_id}")
def delete_module(module_id: str, request: Request):
    path = request.app.state.modules_path
    modules = request.app.state.modules
    before = len(modules["modules"])
    modules["modules"] = [m for m in modules["modules"] if m["module_id"] != module_id]
    if len(modules["modules"]) == before:
        raise HTTPException(status_code=404, detail="Module not found")
    _write_modules(path, modules)
    request.app.state.modules = modules
    import shutil
    references_root = request.app.state.references_root
    ref_module_dir = os.path.join(references_root, module_id)
    if os.path.isdir(ref_module_dir):
        deleted_refs = os.path.join(os.path.dirname(references_root), "deleted_reference_ranges")
        os.makedirs(deleted_refs, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        shutil.move(ref_module_dir, os.path.join(deleted_refs, f"{module_id}_{ts}"))
    with get_connection(request.app.state.db_path) as conn:
        conn.execute("DELETE FROM markers WHERE module_id=?", (module_id,))
        conn.execute("DELETE FROM modules WHERE module_id=?", (module_id,))
        conn.execute("DELETE FROM zone_references WHERE module_id=?", (module_id,))
        conn.commit()
    return {"module_id": module_id}

# Create new marker data
@router.post("/modules/{module_id}/markers", status_code=201)
def post_marker(module_id: str, body: MarkerCreate, request: Request):
    path = request.app.state.modules_path
    modules = request.app.state.modules
    db_path = request.app.state.db_path
    references_root = request.app.state.references_root
    mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
    if mod is None:
        raise HTTPException(status_code=404, detail="Module not found")
    if any(mk["marker_id"] == body.marker_id for mk in mod["markers"]):
        raise HTTPException(status_code=409, detail="marker_id already exists in this module")
    mod["markers"].append({
        "marker_id": body.marker_id,
        "description": body.description,
        "unit": body.unit,
        "volatility_class": body.volatility_class,
    })
    _write_modules(path, modules)
    request.app.state.modules = modules
    # Write reference range JSON
    ref_dir = os.path.join(references_root, module_id)
    os.makedirs(ref_dir, exist_ok=True)
    ref_data = {
        "module_id": module_id,
        "marker_id": body.marker_id,
        "generic": {
            "healthy_min": body.healthy_min,
            "healthy_max": body.healthy_max,
            "vulnerability_margin": body.vulnerability_margin,
        },
    }
    with open(os.path.join(ref_dir, f"{body.marker_id}.json"), "w", encoding="utf-8") as f:
        json.dump(ref_data, f, indent=2)
    # Upsert generic zone_references row and insert into markers table
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO zone_references (module_id, marker_id, sex, age, healthy_min, healthy_max, vulnerability_margin) VALUES (?, ?, NULL, NULL, ?, ?, ?)",
            (module_id, body.marker_id, body.healthy_min, body.healthy_max, body.vulnerability_margin),
        )
        conn.execute(
            "INSERT INTO markers (module_id, marker_id, description, unit, volatility_class) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(module_id, marker_id) DO UPDATE SET description=excluded.description, unit=excluded.unit, volatility_class=excluded.volatility_class",
            (module_id, body.marker_id, body.description, body.unit, body.volatility_class),
        )
        conn.commit()
    return {"module_id": module_id, "marker_id": body.marker_id}

# Add new marker data to module
@router.put("/modules/{module_id}/markers/{marker_id}")
def put_marker(module_id: str, marker_id: str, body: MarkerUpdate, request: Request):
    path = request.app.state.modules_path
    modules = request.app.state.modules
    db_path = request.app.state.db_path
    references_root = request.app.state.references_root
    mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
    if mod is None:
        raise HTTPException(status_code=404, detail="Module not found")
    mk = next((mk for mk in mod["markers"] if mk["marker_id"] == marker_id), None)
    if mk is None:
        raise HTTPException(status_code=404, detail="Marker not found")
    mk["description"] = body.description
    mk["unit"] = body.unit
    mk["volatility_class"] = body.volatility_class
    _write_modules(path, modules)
    request.app.state.modules = modules
    # Overwrite reference range JSON
    ref_path = os.path.join(references_root, module_id, f"{marker_id}.json")
    if os.path.isfile(ref_path):
        with open(ref_path, "r", encoding="utf-8") as f:
            ref_data = json.load(f)
    else:
        ref_data = {"module_id": module_id, "marker_id": marker_id}
    ref_data["generic"] = {
        "healthy_min": body.healthy_min,
        "healthy_max": body.healthy_max,
        "vulnerability_margin": body.vulnerability_margin,
    }
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(ref_data, f, indent=2)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO zone_references (module_id, marker_id, sex, age, healthy_min, healthy_max, vulnerability_margin) VALUES (?, ?, NULL, NULL, ?, ?, ?)",
            (module_id, marker_id, body.healthy_min, body.healthy_max, body.vulnerability_margin),
        )
        conn.execute(
            "UPDATE markers SET description=?, unit=?, volatility_class=? WHERE module_id=? AND marker_id=?",
            (body.description, body.unit, body.volatility_class, module_id, marker_id),
        )
        conn.commit()
    return {"module_id": module_id, "marker_id": marker_id}

# Delete existing marker data
@router.delete("/modules/{module_id}/markers/{marker_id}")
def delete_marker(module_id: str, marker_id: str, request: Request):
    path = request.app.state.modules_path
    modules = request.app.state.modules
    mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
    if mod is None:
        raise HTTPException(status_code=404, detail="Module not found")
    before = len(mod["markers"])
    mod["markers"] = [mk for mk in mod["markers"] if mk["marker_id"] != marker_id]
    if len(mod["markers"]) == before:
        raise HTTPException(status_code=404, detail="Marker not found")
    _write_modules(path, modules)
    request.app.state.modules = modules
    import shutil
    references_root = request.app.state.references_root
    ref_path = os.path.join(references_root, module_id, f"{marker_id}.json")
    if os.path.isfile(ref_path):
        deleted_refs = os.path.join(os.path.dirname(references_root), "deleted_reference_ranges", module_id)
        os.makedirs(deleted_refs, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        shutil.move(ref_path, os.path.join(deleted_refs, f"{marker_id}_{ts}.json"))
    with get_connection(request.app.state.db_path) as conn:
        conn.execute("DELETE FROM markers WHERE module_id=? AND marker_id=?", (module_id, marker_id))
        conn.execute("DELETE FROM zone_references WHERE module_id=? AND marker_id=? AND sex IS NULL AND age IS NULL", (module_id, marker_id))
        conn.commit()
    return {"module_id": module_id, "marker_id": marker_id}

# List all datasets that exists for a subject
@router.get("/subjects/{subject_id}/datasets")
def get_datasets(subject_id: str, request: Request):
    rawdata_root = request.app.state.rawdata_root
    subject_dir = os.path.join(rawdata_root, subject_id)
    if not os.path.isdir(subject_dir):
        raise HTTPException(status_code=404, detail="Subject not found")
    datasets = []
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
            datasets.append({
                "module_id": module_id,
                "marker_id": marker_id,
                "entry_count": len(index.get("entries", [])),
            })
    return datasets

# Get full table of datapoints for one subject/module/marker
@router.get("/subjects/{subject_id}/datasets/{module_id}/{marker_id}")
def get_dataset(subject_id: str, module_id: str, marker_id: str, request: Request):
    rawdata_root = request.app.state.rawdata_root
    marker_dir = os.path.join(rawdata_root, subject_id, module_id, marker_id)
    index_path = os.path.join(marker_dir, "index.json")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    rows = []
    for entry in index.get("entries", []):
        file_path = os.path.join(marker_dir, entry["file"])
        if not os.path.isfile(file_path):
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            dp = json.load(f)
        rows.append({
            "measured_at": dp.get("measured_at"),
            "value": dp.get("value"),
            "unit": dp.get("unit"),
            "data_quality": dp.get("data_quality"),
        })
    return rows

# Add new datapoint via filling out the form
@router.post("/subjects/{subject_id}/datasets/{module_id}/{marker_id}", status_code=201)
def post_datapoint(subject_id: str, module_id: str, marker_id: str, body: DatapointCreate, request:       
Request):
    rawdata_root = request.app.state.rawdata_root
    marker_dir = os.path.join(rawdata_root, subject_id, module_id, marker_id)
    os.makedirs(marker_dir, exist_ok=True)
    index_path = os.path.join(marker_dir, "index.json")
    # Load or create index
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"subject_id": subject_id, "module_id": module_id, "marker_id": marker_id, "entries": []} 
    # Build filename from timestamp
    safe_ts = body.measured_at.replace(":", "-").replace("+", "").rstrip("Z") + "Z"
    filename = f"{safe_ts}.json"
    if any(e["file"] == filename for e in index["entries"]):
        raise HTTPException(status_code=409, detail="A datapoint with this timestamp already exists")
    # Write datapoint file
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    dp = {
        "schema_version": "1.0",
        "module_id": module_id,
        "marker_id": marker_id,
        "subject_id": subject_id,
        "measured_at": body.measured_at,
        "value": body.value,
        "unit": body.unit,
        "data_quality": body.data_quality,
        "created_at": created_at,
    }
    with open(os.path.join(marker_dir, filename), "w", encoding="utf-8") as f:
        json.dump(dp, f, indent=2)
    # Append to index
    index["entries"].append({"measured_at": body.measured_at, "file": filename})
    index["entries"].sort(key=lambda e: e["measured_at"])
    _save_index(index_path, index)
    table = _datapoint_table(subject_id, module_id, marker_id)
    with get_connection(request.app.state.db_path) as conn:
        _ensure_datapoint_table(conn, table)
        conn.execute(
            f'INSERT INTO "{table}" (measured_at, value, unit, data_quality, created_at) '
            f'VALUES (?, ?, ?, ?, ?) ON CONFLICT(measured_at) DO UPDATE SET '
            f'value=excluded.value, unit=excluded.unit, data_quality=excluded.data_quality',
            (body.measured_at, body.value, body.unit, body.data_quality, created_at),
        )
        conn.commit()
    return {"file": filename}

#Add new datapoint via uploading JSON file
@router.post("/subjects/{subject_id}/datasets/{module_id}/{marker_id}/upload", status_code=201)
async def upload_datapoint(subject_id: str, module_id: str, marker_id: str, request: Request, file:       
UploadFile = File(...)):
    rawdata_root = request.app.state.rawdata_root
    marker_dir = os.path.join(rawdata_root, subject_id, module_id, marker_id)
    os.makedirs(marker_dir, exist_ok=True)
    index_path = os.path.join(marker_dir, "index.json")
    content = await file.read()
    try:
        dp = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Uploaded file is not valid JSON")
    for key in ("measured_at", "value", "unit"):
        if key not in dp:
            raise HTTPException(status_code=422, detail=f"Missing required field: {key}")
    # Load or create index
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    else:
        index = {"subject_id": subject_id, "module_id": module_id, "marker_id": marker_id, "entries": []}
    safe_ts = dp["measured_at"].replace(":", "-").replace("+", "").rstrip("Z") + "Z"
    filename = f"{safe_ts}.json"
    if any(e["file"] == filename for e in index["entries"]):
        raise HTTPException(status_code=409, detail="A datapoint with this timestamp already exists")
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with open(os.path.join(marker_dir, filename), "wb") as f:
        f.write(content)
    index["entries"].append({"measured_at": dp["measured_at"], "file": filename})
    index["entries"].sort(key=lambda e: e["measured_at"])
    _save_index(index_path, index)
    table = _datapoint_table(subject_id, module_id, marker_id)
    with get_connection(request.app.state.db_path) as conn:
        _ensure_datapoint_table(conn, table)
        conn.execute(
            f'INSERT INTO "{table}" (measured_at, value, unit, data_quality, created_at) '
            f'VALUES (?, ?, ?, ?, ?) ON CONFLICT(measured_at) DO UPDATE SET '
            f'value=excluded.value, unit=excluded.unit, data_quality=excluded.data_quality',
            (dp["measured_at"], dp["value"], dp.get("unit"), dp.get("data_quality", "good"), created_at),
        )
        conn.commit()
    return {"file": filename}

# Delete a single datapoint by measured_at
@router.delete("/subjects/{subject_id}/datasets/{module_id}/{marker_id}/{measured_at}")
def delete_datapoint(subject_id: str, module_id: str, marker_id: str, measured_at: str, request: Request):
    rawdata_root = request.app.state.rawdata_root
    marker_dir = os.path.join(rawdata_root, subject_id, module_id, marker_id)
    index_path = os.path.join(marker_dir, "index.json")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    entry = next((e for e in index["entries"] if e["measured_at"] == measured_at), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Datapoint not found")
    file_path = os.path.join(marker_dir, entry["file"])
    if os.path.isfile(file_path):
        import shutil
        silo = os.path.join(os.path.dirname(rawdata_root), "deleted_datapoints", subject_id, module_id, marker_id)
        os.makedirs(silo, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        silo_name = entry["file"].replace(".json", f"_{ts}.json")
        shutil.move(file_path, os.path.join(silo, silo_name))
    index["entries"] = [e for e in index["entries"] if e["measured_at"] != measured_at]
    _save_index(index_path, index)
    table = _datapoint_table(subject_id, module_id, marker_id)
    with get_connection(request.app.state.db_path) as conn:
        conn.execute(f'DELETE FROM "{table}" WHERE measured_at=?', (measured_at,))
        conn.commit()
    return {"measured_at": measured_at}

# Delete an entire marker dataset
@router.delete("/subjects/{subject_id}/datasets/{module_id}/{marker_id}")
def delete_dataset(subject_id: str, module_id: str, marker_id: str, request: Request):
    import shutil
    rawdata_root = request.app.state.rawdata_root
    marker_dir = os.path.join(rawdata_root, subject_id, module_id, marker_id)
    if not os.path.isdir(marker_dir):
        raise HTTPException(status_code=404, detail="Dataset not found")
    silo = os.path.join(os.path.dirname(rawdata_root), "deleted_datasets", subject_id, module_id)
    os.makedirs(silo, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    shutil.move(marker_dir, os.path.join(silo, f"{marker_id}_{ts}"))
    table = _datapoint_table(subject_id, module_id, marker_id)
    with get_connection(request.app.state.db_path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.commit()
    return {"module_id": module_id, "marker_id": marker_id}

#  Return calculation results needed to post timegraph and also save them to the database
@router.post("/timegraph")
def post_timegraph(body: TimegraphRequest, request: Request):
    db_path = request.app.state.db_path
    rawdata_root = request.app.state.rawdata_root
    reports_root = request.app.state.reports_root
# Convert timeframe strings to timezone-aware datetime objects
    try:
        from_time = datetime.fromisoformat(body.timeframe.start_time.replace("Z", "+00:00"))
        to_time   = datetime.fromisoformat(body.timeframe.end_time.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid timestamp format: {e}")
# Read raw datapoints
    try: 
        datapoints = read_timeseries(
            rawdata_root,
            body.subject_id,
            body.module_id,
            body.marker_id,
            from_time,
            to_time,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail = f"Could not read datapoints: {e}")
    if not datapoints:
        raise HTTPException(status_code=404, detail = "No datapoints found within the requested timeframe")
    # Run trajectory computation
    zone_boundaries_dict = {
        "healthy_min": body.zone_boundaries.healthy_min,
        "healthy_max": body.zone_boundaries.healthy_max,
        "vulnerability_margin": body.zone_boundaries.vulnerability_margin,
    }
    try:
        trajectory_result = compute_trajectory(
            datapoints,
            zone_boundaries_dict,
            body.fitting.polynomial_degree,
        )
    except ValueError as e:
            raise HTTPException(status_code=422, detail = f"trajectory could not be computed: {e}")
    # Build report metadata and pass to save_timegraph_report()
    subject_id = body.subject_id
    requested_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    date_str = requested_at.split("T")[0] # Extract just the data
    short_uuid = str(uuid4())[:8]  # First 8 characters of UUID
    report_id = str(f"{subject_id}-{date_str}-{short_uuid}") # Resolves as: "subject_001-2026-02-23-550e8400"
    timeframe_dict = {"from": body.timeframe.start_time, "to": body.timeframe.end_time}
    fitting_dict   = {"polynomial_degree": body.fitting.polynomial_degree}

    save_timegraph_report(
        db_path = db_path,
        reports_root=reports_root,
        report_id=report_id,
        subject_id=body.subject_id,
        module_id=body.module_id,
        marker_id=body.marker_id,
        requested_at=requested_at,
        timeframe=timeframe_dict,
        zone_boundaries=zone_boundaries_dict,
        fitting=fitting_dict,
        trajectory_result=trajectory_result,
    )
    return {
        "report_id": report_id,
        "datapoints": trajectory_result["datapoints"],
        "fit_metadata": trajectory_result["fit_metadata"]
    }
