# All GraphQL Query resolvers.
# Each resolver mirrors an existing REST GET endpoint so the GraphQL layer
# has feature parity with REST before REST is eventually deprecated.

from __future__ import annotations
import os
import json
from datetime import date
from typing import Optional

import strawberry

from backend.startup.database_logistics import get_connection, _datapoint_table
from backend.graphql.context import AppContext
from backend.graphql.types.subject import Subject, ZoneReference
from backend.graphql.types.module import Module, Marker, DemographicZone
from backend.graphql.types.datapoint import Datapoint, Dataset
from backend.graphql.types.analysis import AnalysisJob, AnalysisMethodInfo, JobStatus
from backend.graphql.types.markerset import (
    MarkersetTemplate, MarkersetInstance,
    feature_config_from_dict,
)


@strawberry.type
class Query:

    # ── Subjects ──────────────────────────────────────────────────────────────

    @strawberry.field(description="List all subjects.")
    def subjects(self, info: strawberry.types.Info[AppContext, None]) -> list[Subject]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM subjects ORDER BY subject_id"
            ).fetchall()
        return [Subject.from_row(dict(r)) for r in rows]

    @strawberry.field(description="Fetch a single subject by ID.")
    def subject(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
    ) -> Optional[Subject]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM subjects WHERE subject_id = ?", (subject_id,)
            ).fetchone()
        return Subject.from_row(dict(row)) if row else None

    @strawberry.field(
        description=(
            "Return age/sex-interpolated zone boundary suggestions for a given "
            "subject and marker. Mirrors GET /subjects/{id}/zone-reference/{module}/{marker}."
        )
    )
    def zone_reference(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
        module_id: str,
        marker_id: str,
    ) -> Optional[ZoneReference]:
        ctx = info.context
        db_path = ctx.db_path

        with get_connection(db_path) as conn:
            subject = conn.execute(
                "SELECT sex, dob FROM subjects WHERE subject_id = ?", (subject_id,)
            ).fetchone()
        if subject is None:
            return None

        sex = subject["sex"]
        dob = subject["dob"]
        age = None
        if dob:
            try:
                birth = date.fromisoformat(dob[:10])
                today = date.today()
                age = today.year - birth.year - (
                    (today.month, today.day) < (birth.month, birth.day)
                )
            except ValueError:
                pass

        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT age, healthy_min, healthy_max, vulnerability_margin "
                "FROM zone_references "
                "WHERE module_id = ? AND marker_id = ? AND sex = ? AND age IS NOT NULL "
                "ORDER BY age",
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
                            lo["vulnerability_margin"] + t * (hi["vulnerability_margin"] - lo["vulnerability_margin"]),
                        )
                        break

        if result is None:
            with get_connection(db_path) as conn:
                generic = conn.execute(
                    "SELECT healthy_min, healthy_max, vulnerability_margin "
                    "FROM zone_references "
                    "WHERE module_id = ? AND marker_id = ? AND sex IS NULL AND age IS NULL",
                    (module_id, marker_id),
                ).fetchone()
            if generic is None:
                return None
            result = (generic["healthy_min"], generic["healthy_max"], generic["vulnerability_margin"])
            note = "No sex/age-specific reference data available; using generic values."

        return ZoneReference(
            healthy_min          = result[0],
            healthy_max          = result[1],
            vulnerability_margin = result[2],
            note                 = note,
        )

    # ── Modules / Markers ─────────────────────────────────────────────────────

    @strawberry.field(description="List all modules with their markers.")
    def modules(self, info: strawberry.types.Info[AppContext, None]) -> list[Module]:
        modules_data = info.context.modules.get("modules", [])
        return [Module.from_dict(m) for m in modules_data]

    @strawberry.field(description="Fetch a single module by ID.")
    def module(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
    ) -> Optional[Module]:
        modules_data = info.context.modules.get("modules", [])
        mod = next((m for m in modules_data if m["module_id"] == module_id), None)
        return Module.from_dict(mod) if mod else None

    @strawberry.field(description="List all demographic zone rows for a marker.")
    def demographic_zones(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        marker_id: str,
    ) -> list[DemographicZone]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            rows = conn.execute(
                "SELECT sex, age, healthy_min, healthy_max, vulnerability_margin "
                "FROM zone_references "
                "WHERE module_id = ? AND marker_id = ? AND sex IS NOT NULL "
                "ORDER BY sex ASC, age ASC",
                (module_id, marker_id),
            ).fetchall()
        return [
            DemographicZone(
                sex                  = r["sex"],
                age                  = r["age"],
                healthy_min          = r["healthy_min"],
                healthy_max          = r["healthy_max"],
                vulnerability_margin = r["vulnerability_margin"],
            )
            for r in rows
        ]

    # ── Datapoints / Datasets ─────────────────────────────────────────────────

    @strawberry.field(description="List dataset summaries for a subject (entry count per marker).")
    def datasets(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
    ) -> list[Dataset]:
        ctx = info.context
        subject_dir = os.path.join(ctx.rawdata_root, subject_id)
        if not os.path.isdir(subject_dir):
            return []
        result = []
        for module_id in os.listdir(subject_dir):
            module_dir = os.path.join(subject_dir, module_id)
            if not os.path.isdir(module_dir):
                continue
            for marker_id in os.listdir(module_dir):
                index_path = os.path.join(module_dir, marker_id, "index.json")
                if not os.path.isfile(index_path):
                    continue
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
                result.append(Dataset(
                    module_id   = module_id,
                    marker_id   = marker_id,
                    entry_count = len(index.get("entries", [])),
                ))
        return result

    @strawberry.field(description="Fetch datapoints for one subject/module/marker, with optional time filter.")
    def datapoints(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
        module_id: str,
        marker_id: str,
        from_time: Optional[str] = None,
        to_time:   Optional[str] = None,
    ) -> list[Datapoint]:
        ctx = info.context
        table = _datapoint_table(subject_id, module_id, marker_id)

        with get_connection(ctx.db_path) as conn:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                return []

            query      = f'SELECT measured_at, value, unit, data_quality FROM "{table}"'
            params: list = []
            conditions: list[str] = []
            if from_time:
                conditions.append("measured_at >= ?")
                params.append(from_time)
            if to_time:
                conditions.append("measured_at <= ?")
                params.append(to_time)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY measured_at"

            rows = conn.execute(query, params).fetchall()

        return [
            Datapoint(
                measured_at  = r["measured_at"],
                value        = r["value"],
                unit         = r["unit"]         or "",
                data_quality = r["data_quality"] or "good",
            )
            for r in rows
        ]

    # ── Analysis method registry ──────────────────────────────────────────────

    @strawberry.field(description="List all analysis methods from the registry (includes stubs).")
    def analysis_methods(
        self,
        info: strawberry.types.Info[AppContext, None],
    ) -> list[AnalysisMethodInfo]:
        methods_data = info.context.methods.get("methods", [])
        return [
            AnalysisMethodInfo(
                method_id             = m["method_id"],
                method_name           = m["method_name"],
                description           = m.get("description", ""),
                status                = m.get("status", "stub"),
                accepts_single_marker = m.get("accepts_single_marker", False),
                accepts_markerset     = m.get("accepts_markerset", False),
                min_markers           = m.get("min_markers"),
                max_markers           = m.get("max_markers"),
                params_schema         = m.get("params_schema", "none"),
                output_type           = m.get("output_type", ""),
            )
            for m in methods_data
        ]

    # ── Markersets ────────────────────────────────────────────────────────────

    @strawberry.field(description="List all markerset templates.")
    def markerset_templates(
        self,
        info: strawberry.types.Info[AppContext, None],
    ) -> list[MarkersetTemplate]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            rows = conn.execute(
                "SELECT markerset_id, name, description, markers_json, created_at "
                "FROM markerset_templates ORDER BY created_at DESC"
            ).fetchall()
        return [
            MarkersetTemplate(
                markerset_id = r["markerset_id"],
                name         = r["name"],
                description  = r["description"],
                markers      = [feature_config_from_dict(m) for m in json.loads(r["markers_json"])],
                created_at   = r["created_at"],
            )
            for r in rows
        ]

    @strawberry.field(description="Fetch a single markerset template by ID.")
    def markerset_template(
        self,
        info:         strawberry.types.Info[AppContext, None],
        markerset_id: str,
    ) -> Optional[MarkersetTemplate]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            row = conn.execute(
                "SELECT markerset_id, name, description, markers_json, created_at "
                "FROM markerset_templates WHERE markerset_id = ?",
                (markerset_id,),
            ).fetchone()
        if not row:
            return None
        return MarkersetTemplate(
            markerset_id = row["markerset_id"],
            name         = row["name"],
            description  = row["description"],
            markers      = [feature_config_from_dict(m) for m in json.loads(row["markers_json"])],
            created_at   = row["created_at"],
        )

    @strawberry.field(description="List markerset instances for a subject.")
    def markerset_instances(
        self,
        info:       strawberry.types.Info[AppContext, None],
        subject_id: str,
    ) -> list[MarkersetInstance]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            rows = conn.execute(
                "SELECT instance_id, subject_id, markerset_id, name, overrides_json, created_at "
                "FROM markerset_instances WHERE subject_id = ? ORDER BY created_at DESC",
                (subject_id,),
            ).fetchall()

            result = []
            for r in rows:
                overrides = json.loads(r["overrides_json"])

                # Resolve full marker list (template + overrides, or custom)
                if r["markerset_id"]:
                    tmpl = conn.execute(
                        "SELECT markers_json FROM markerset_templates WHERE markerset_id = ?",
                        (r["markerset_id"],),
                    ).fetchone()
                    base = json.loads(tmpl["markers_json"]) if tmpl else []
                    override_map = {f"{o['module_id']}/{o['marker_id']}": o for o in overrides}
                    merged = []
                    for m in base:
                        key = f"{m['module_id']}/{m['marker_id']}"
                        merged.append({**m, **override_map[key]} if key in override_map else m)
                else:
                    merged = overrides

                result.append(MarkersetInstance(
                    instance_id  = r["instance_id"],
                    subject_id   = r["subject_id"],
                    markerset_id = r["markerset_id"],
                    name         = r["name"],
                    markers      = [feature_config_from_dict(m) for m in merged],
                    created_at   = r["created_at"],
                ))
        return result

    # ── Analysis reports ──────────────────────────────────────────────────────

    @strawberry.field(description="List past analysis report metadata for a subject.")
    def analysis_reports(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
    ) -> list[AnalysisJob]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            rows = conn.execute(
                "SELECT report_id, requested_at FROM timegraph_reports "
                "WHERE subject_id = ? ORDER BY requested_at DESC",
                (subject_id,),
            ).fetchall()
        # Historical reports are always COMPLETED. Full result data is not stored
        # in SQLite — load the report JSON from the filesystem if needed.
        return [
            AnalysisJob(
                job_id        = r["report_id"],
                status        = JobStatus.COMPLETED,
                progress      = 1.0,
                created_at    = r["requested_at"],
                result        = None,
                error_message = None,
            )
            for r in rows
        ]
