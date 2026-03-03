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
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.core.storage.data_reader import read_timeseries
from backend.startup.database_logistics import get_connection
from backend.core.analysis.trajectory_computer import compute_trajectory
from backend.startup.database_logistics import get_connection
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

#Routes

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
