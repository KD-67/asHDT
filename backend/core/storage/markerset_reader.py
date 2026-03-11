# Loads a markerset instance from the DB and resolves its full marker configuration,
# including per-marker zone boundaries derived from the subject's demographics.
# For template-based instances, sparse overrides are merged onto the template base.

from __future__ import annotations
import json
import logging
from datetime import date

from backend.startup.database_logistics import get_connection

logger = logging.getLogger(__name__)


def _zone_boundaries_for_marker(
    conn,
    subject_id: str,
    module_id:  str,
    marker_id:  str,
) -> dict:
    """
    Returns age/sex-interpolated zone boundaries for one subject+marker pair.
    Falls back to generic (sex=NULL, age=NULL) row if no demographic data is available.
    Raises ValueError if no zone reference exists at all.
    """
    row = conn.execute(
        "SELECT sex, dob FROM subjects WHERE subject_id = ?", (subject_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Subject '{subject_id}' not found.")

    sex = row["sex"]
    dob = row["dob"]
    age = None
    if dob:
        try:
            birth = date.fromisoformat(dob[:10])
            today = date.today()
            age   = today.year - birth.year - (
                (today.month, today.day) < (birth.month, birth.day)
            )
        except ValueError:
            pass

    rows = conn.execute(
        "SELECT age, healthy_min, healthy_max, vulnerability_margin "
        "FROM zone_references "
        "WHERE module_id = ? AND marker_id = ? AND sex = ? AND age IS NOT NULL "
        "ORDER BY age",
        (module_id, marker_id, sex),
    ).fetchall()

    result = None
    if rows and age is not None:
        ages = [r["age"] for r in rows]
        if age <= ages[0]:
            r      = rows[0]
            result = (r["healthy_min"], r["healthy_max"], r["vulnerability_margin"])
        elif age >= ages[-1]:
            r      = rows[-1]
            result = (r["healthy_min"], r["healthy_max"], r["vulnerability_margin"])
        else:
            for i in range(len(rows) - 1):
                if ages[i] <= age <= ages[i + 1]:
                    lo, hi = rows[i], rows[i + 1]
                    t      = (age - ages[i]) / (ages[i + 1] - ages[i])
                    result = (
                        lo["healthy_min"]          + t * (hi["healthy_min"]          - lo["healthy_min"]),
                        lo["healthy_max"]          + t * (hi["healthy_max"]          - lo["healthy_max"]),
                        lo["vulnerability_margin"] + t * (hi["vulnerability_margin"] - lo["vulnerability_margin"]),
                    )
                    break

    if result is None:
        generic = conn.execute(
            "SELECT healthy_min, healthy_max, vulnerability_margin "
            "FROM zone_references "
            "WHERE module_id = ? AND marker_id = ? AND sex IS NULL AND age IS NULL",
            (module_id, marker_id),
        ).fetchone()
        if generic is None:
            raise ValueError(
                f"No zone reference found for {module_id}/{marker_id}. "
                "Add zone boundaries before running composite analysis."
            )
        result = (generic["healthy_min"], generic["healthy_max"], generic["vulnerability_margin"])

    return {
        "healthy_min":          result[0],
        "healthy_max":          result[1],
        "vulnerability_margin": result[2],
    }


def resolve_markerset_markers(
    db_path:          str,
    subject_id:       str,
    instance_id:      str | None         = None,
    raw_marker_refs:  list[dict] | None  = None,
) -> list[dict]:
    """
    Resolves a markerset instance or ad-hoc marker_refs into a fully-configured
    marker list, adding per-marker zone_boundaries from the DB.

    Exactly one of instance_id / raw_marker_refs must be provided.

    Returns:
        list of dicts (one per active marker):
            {
                "module_id":    str,
                "marker_id":    str,
                "weight":       float,
                "active":       bool,
                "transform":    dict,   # {type, window_hours, lag_hours}
                "missing_data": str,
                "zone_boundaries": {healthy_min, healthy_max, vulnerability_margin},
            }
    """
    if (instance_id is None) == (raw_marker_refs is None):
        raise ValueError("Exactly one of instance_id or raw_marker_refs must be provided.")

    with get_connection(db_path) as conn:

        if instance_id is not None:
            inst = conn.execute(
                "SELECT markerset_id, overrides_json FROM markerset_instances "
                "WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
            if inst is None:
                raise ValueError(f"Markerset instance '{instance_id}' not found.")

            overrides = json.loads(inst["overrides_json"])

            if inst["markerset_id"]:
                tmpl = conn.execute(
                    "SELECT markers_json FROM markerset_templates WHERE markerset_id = ?",
                    (inst["markerset_id"],),
                ).fetchone()
                if tmpl is None:
                    raise ValueError(f"Markerset template '{inst['markerset_id']}' not found.")
                base_markers = json.loads(tmpl["markers_json"])

                # Merge: overrides are applied by (module_id, marker_id) key
                override_map = {
                    f"{o['module_id']}/{o['marker_id']}": o for o in overrides
                }
                merged = []
                for m in base_markers:
                    key    = f"{m['module_id']}/{m['marker_id']}"
                    merged.append({**m, **override_map[key]} if key in override_map else m)
            else:
                # Custom instance — overrides IS the full marker list
                merged = overrides

        else:
            # Ad-hoc multi-marker: apply default feature config
            merged = [
                {
                    "module_id":    r["module_id"],
                    "marker_id":    r["marker_id"],
                    "weight":       r.get("weight", 1.0),
                    "active":       True,
                    "transform":    {"type": "none", "window_hours": None, "lag_hours": None},
                    "missing_data": "interpolate",
                }
                for r in raw_marker_refs  # type: ignore[union-attr]
            ]

        # Attach per-marker zone boundaries (active markers only)
        result = []
        for m in merged:
            if not m.get("active", True):
                continue
            zone_bnd = _zone_boundaries_for_marker(
                conn, subject_id, m["module_id"], m["marker_id"]
            )
            result.append({**m, "zone_boundaries": zone_bnd})

    return result
