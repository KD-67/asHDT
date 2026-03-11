# ARQ worker task functions.
#
# Each function here is a standalone async task that runs in a separate worker
# process (started with: arq backend.workers.settings.WorkerSettings).
#
# HOW TO ADD A NEW ANALYSIS METHOD:
#   1. Add a new async function here following the same pattern
#   2. Register it in WorkerSettings.functions (settings.py)
#   3. Add the enum value to AnalysisMethod in types/analysis.py
#   4. Handle it in the submit_analysis mutation (mutations.py)
#   5. Define its result type and add it to the AnalysisResult union (types/analysis.py)

from __future__ import annotations
import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)


async def run_trajectory_analysis(
    ctx: dict,
    *,
    job_id:            str,
    subject_id:        str,
    marker_refs:       list[dict],  # [{module_id, marker_id} for single; full config + zone_boundaries for composite]
    use_composite:     bool,
    timeframe:         dict,
    trajectory_params: dict,
    db_path:           str,
    rawdata_root:      str,
    reports_root:      str,
    created_at:        str,
) -> dict:
    """
    Performs the full trajectory analysis pipeline.

    Two modes selected by use_composite:
        False — single-marker direct flow: reads raw timeseries, uses trajectory_params
                zone_boundaries for normalisation.
        True  — composite flow: reads each marker's timeseries, applies feature
                transforms, normalises to h, builds weighted composite, then runs
                trajectory on the composite health score.

    Published pub/sub messages (channel: "job:{job_id}"):
        {"status": "running",   "progress": 0.1–0.85}
        {"status": "completed", "progress": 1.0, "report_id": "...", "result": {...}, ...}
        {"status": "failed",    "progress": null, "error": "..."}
    """
    redis = ctx["redis"]

    async def publish(payload: dict) -> None:
        await redis.publish(f"job:{job_id}", json.dumps(payload))

    try:
        await publish({"status": "running", "progress": 0.1})

        from backend.core.storage.data_reader import read_timeseries
        from backend.core.analysis.trajectory_computer import compute_trajectory
        from backend.core.output.report_generator import save_timegraph_report

        from_time = datetime.fromisoformat(timeframe["start_time"].replace("Z", "+00:00"))
        to_time   = datetime.fromisoformat(timeframe["end_time"].replace("Z", "+00:00"))

        await publish({"status": "running", "progress": 0.3})

        if use_composite:
            # ── Composite mode: multi-marker → weighted composite h ────────────
            from backend.core.storage.data_reader import read_multi_marker_timeseries
            from backend.core.analysis.composite_builder import (
                build_composite_timeseries,
                composite_zone_boundaries,
            )

            marker_timeseries = read_multi_marker_timeseries(
                rawdata_root, subject_id, marker_refs, from_time, to_time
            )

            await publish({"status": "running", "progress": 0.5})

            datapoints = build_composite_timeseries(marker_timeseries)
            if not datapoints:
                raise ValueError("Composite timeseries is empty — no data in the requested timeframe.")

            zone_boundaries = composite_zone_boundaries(
                trajectory_params["vulnerability_margin"]
            )

            # For the report: use "composite" as module_id; list all marker refs
            report_module_id = "composite"
            report_marker_ids = [
                f"{m['module_id']}/{m['marker_id']}"
                for m in marker_refs
                if m.get("active", True)
            ]
            report_marker_id = report_marker_ids[0] if report_marker_ids else "composite"

        else:
            # ── Single-marker direct mode ──────────────────────────────────────
            module_id = marker_refs[0]["module_id"]
            marker_id = marker_refs[0]["marker_id"]

            datapoints = read_timeseries(
                rawdata_root, subject_id, module_id, marker_id, from_time, to_time
            )
            if not datapoints:
                raise ValueError(
                    f"No datapoints found for {subject_id}/{module_id}/{marker_id} "
                    f"in the requested timeframe."
                )

            zone_boundaries = {
                "healthy_min":          trajectory_params["healthy_min"],
                "healthy_max":          trajectory_params["healthy_max"],
                "vulnerability_margin": trajectory_params["vulnerability_margin"],
            }

            report_module_id  = module_id
            report_marker_id  = marker_id
            report_marker_ids = [marker_id]

        await publish({"status": "running", "progress": 0.6})

        result = compute_trajectory(
            datapoints,
            zone_boundaries,
            trajectory_params["polynomial_degree"],
        )

        await publish({"status": "running", "progress": 0.85})

        requested_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        date_str     = requested_at.split("T")[0]
        short_uuid   = str(uuid4())[:8]
        report_id    = f"{subject_id}-{date_str}-{short_uuid}"

        save_timegraph_report(
            db_path           = db_path,
            reports_root      = reports_root,
            report_id         = report_id,
            subject_id        = subject_id,
            module_id         = report_module_id,
            marker_id         = report_marker_id,
            requested_at      = requested_at,
            timeframe         = {"from": timeframe["start_time"], "to": timeframe["end_time"]},
            zone_boundaries   = zone_boundaries,
            fitting           = {"polynomial_degree": trajectory_params["polynomial_degree"]},
            trajectory_result = result,
        )

        completed_payload = {
            "status":       "completed",
            "progress":     1.0,
            "report_id":    report_id,
            "result":       result,
            "subject_id":   subject_id,
            "module_id":    report_module_id,
            "marker_ids":   report_marker_ids,
            "requested_at": requested_at,
            "created_at":   created_at,
        }
        await redis.setex(f"job_result:{job_id}", 3600, json.dumps(completed_payload))
        await publish(completed_payload)

        return {"report_id": report_id}

    except Exception as exc:
        logger.error("Trajectory analysis failed for job %s: %s", job_id, exc, exc_info=True)
        await publish({
            "status":   "failed",
            "progress": None,
            "error":    str(exc),
        })
        raise
