# Simultaneously updates both the filesystem and the database every time a new analysis is performed. 
#   -In /backend/data/reports: creates a json  with the timestamp, user-inputs, and computed results. Creates new subject-specific directory if one does not already exist. 
#   -In timegraph_reports SQLite db table: creates new entry with all inputs needed to remake the 
#       exact same calculation (assuming raw_data files remain unchanged) 

import json
import os
from startup.database_logistics import get_connection

# All context needed to describe a report
def save_timegraph_report(
    db_path: str,
    reports_root: str,
    report_id: str,
    subject_id: str,
    module_id: str,
    marker_id: str,
    requested_at: str,
    timeframe: dict,
    zone_boundaries: dict,
    fitting: dict,
    trajectory_result: dict,
) -> None:
    # 1. Write the full report JSON to the filesystem
    report_dir = os.path.join(reports_root, subject_id)
    os.makedirs(report_dir, exist_ok=True)

    report_payload = {
        "report_id":       report_id,
        "subject_id":      subject_id,
        "module_id":       module_id,
        "marker_id":       marker_id,
        "requested_at":    requested_at,
        "timeframe":       timeframe,
        "zone_boundaries": zone_boundaries,
        "fitting":         fitting,
        "result":          trajectory_result,
    }

    report_path = os.path.join(report_dir, f"{report_id}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    # 2. Insert metadata row into timegraph_reports
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO timegraph_reports (
                report_id,
                subject_id,
                marker_id,
                module_id,
                requested_at,
                timeframe_from,
                timeframe_to,
                polynomial_degree,
                healthy_min,
                healthy_max,
                vulnerability_margin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                subject_id,
                marker_id,
                module_id,
                requested_at,
                timeframe["from"],
                timeframe["to"],
                fitting["polynomial_degree"],
                zone_boundaries["healthy_min"],
                zone_boundaries["healthy_max"],
                zone_boundaries["vulnerability_margin"],
            ),
        )