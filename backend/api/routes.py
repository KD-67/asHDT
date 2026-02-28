# Defines the endpoints and pydantic request models that the application (app = fastAPI() from main.py) uses.

import os
import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.core.storage.data_reader import read_timeseries
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
    profile_path = os.path.join(request.app.state.rawdata_root, subject_id, "profile.json")
    if not os.path.exists(profile_path):
        raise HTTPException(status_code=404, detail="Subject profile not found")
    with open(profile_path, 'r') as f:
        profile_data = json.load(f)
    return profile_data

#  Return calculation results needed to post timegraph 
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
        # Ensure subject row exists in database, and return data needed for frontend to render chart    
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO subjects (subject_id, created_at) VALUES (?, ?)",
            (body.subject_id, requested_at),
        )
    return {
        "report_id": report_id,
        "datapoints": trajectory_result["datapoints"],
        "fit_metadata": trajectory_result["fit_metadata"]
    }
