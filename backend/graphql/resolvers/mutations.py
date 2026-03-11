# All GraphQL Mutation resolvers.
#
# Organised into sections:
#   1. submitAnalysis      — async compute job dispatch (the architectural centrepiece)
#   2. Subject CRUD        — create / update / delete subjects
#   3. Module / Marker CRUD
#   4. Datapoint CRUD
#   5. Zone reference CRUD

from __future__ import annotations
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import strawberry
from strawberry.exceptions import GraphQLError
from strawberry.file_uploads import Upload

from backend.startup.database_logistics import (
    get_connection,
    _datapoint_table,
    _ensure_datapoint_table,
)
from backend.graphql.context import AppContext
from backend.graphql.types.subject import Subject, ZoneReference
from backend.graphql.types.module import Module, Marker, DemographicZone
from backend.graphql.types.datapoint import Datapoint
from backend.graphql.types.analysis import (
    AnalysisInput,
    AnalysisMethod,
    AnalysisJob,
    JobStatus,
    TrajectoryParamsInput,
)
from backend.graphql.types.markerset import (
    MarkersetTemplate, MarkersetInstance,
    CreateMarkersetTemplateInput, CreateMarkersetInstanceInput,
    feature_config_from_dict, feature_config_input_to_dict,
)
from backend.core.storage.markerset_reader import resolve_markerset_markers


# ── Shared helpers (mirror routes.py helpers) ──────────────────────────────────

def _write_modules(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _save_index(index_path: str, data: dict) -> None:
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_ref_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_ref_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Mutation input types ───────────────────────────────────────────────────────

@strawberry.input
class SubjectInput:
    first_name: str
    last_name:  str
    sex:        str
    dob:        str
    email:      str
    phone:      str
    notes:      str = ""


@strawberry.input
class ModuleInput:
    module_id:   str
    module_name: str = ""
    description: str = ""
    format:      str = "json"


@strawberry.input
class ModuleUpdateInput:
    module_name: str = ""
    description: str = ""


@strawberry.input
class MarkerInput:
    marker_id:            str
    marker_name:          str = ""
    description:          str = ""
    unit:                 str = ""
    volatility_class:     str = ""
    healthy_min:          float = 0.0
    healthy_max:          float = 1.0
    vulnerability_margin: float = 0.2


@strawberry.input
class MarkerUpdateInput:
    marker_name:          str = ""
    description:          str = ""
    unit:                 str = ""
    volatility_class:     str = ""
    healthy_min:          float = 0.0
    healthy_max:          float = 1.0
    vulnerability_margin: float = 0.2


@strawberry.input
class DatapointInput:
    measured_at:  str
    value:        float
    unit:         str
    data_quality: str = "good"


@strawberry.input
class ZoneBoundaryInput:
    healthy_min:          float
    healthy_max:          float
    vulnerability_margin: float


@strawberry.input
class DemographicZoneInput:
    sex:                  str
    age:                  int
    healthy_min:          float
    healthy_max:          float
    vulnerability_margin: float


# ── Mutation root ──────────────────────────────────────────────────────────────

@strawberry.type
class Mutation:

    # ── 1. submitAnalysis ──────────────────────────────────────────────────────

    @strawberry.mutation(
        description=(
            "Enqueue an analysis computation and return immediately with a job_id. "
            "Open a jobStatus subscription with that id to receive real-time progress "
            "and the final result."
        )
    )
    async def submit_analysis(
        self,
        info: strawberry.types.Info[AppContext, None],
        input: AnalysisInput,
    ) -> AnalysisJob:
        ctx = info.context

        if ctx.redis_pool is None:
            raise GraphQLError(
                "Redis is not available. Start Redis and restart the server to enable "
                "async analysis jobs."
            )

        # Validate: exactly one of markerset_id / marker_refs must be set
        has_markerset = input.markerset_id is not None
        has_refs      = input.marker_refs  is not None and len(input.marker_refs) > 0
        if has_markerset == has_refs:
            raise GraphQLError(
                "Exactly one of markerset_id or marker_refs must be provided."
            )

        if input.method == AnalysisMethod.TRAJECTORY:
            if input.trajectory_params is None:
                raise GraphQLError("trajectory_params is required when method=TRAJECTORY.")
        else:
            raise GraphQLError(
                f"Analysis method '{input.method.value}' is not yet implemented. "
                "Currently only TRAJECTORY is supported."
            )

        job_id     = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        timeframe_dict: dict = {
            "start_time": input.timeframe.start_time,
            "end_time":   input.timeframe.end_time,
        }
        params = input.trajectory_params
        trajectory_params_dict: dict = {
            "polynomial_degree":    params.polynomial_degree,
            "healthy_min":          params.healthy_min,
            "healthy_max":          params.healthy_max,
            "vulnerability_margin": params.vulnerability_margin,
        }

        if has_markerset:
            # Resolve markerset instance → fully-configured markers with DB zone boundaries
            try:
                resolved_markers = resolve_markerset_markers(
                    ctx.db_path, input.subject_id, instance_id=input.markerset_id
                )
            except ValueError as e:
                raise GraphQLError(str(e))
            use_composite = True
        else:
            # Ad-hoc marker_refs
            resolved_markers = [
                {"module_id": m.module_id, "marker_id": m.marker_id}
                for m in input.marker_refs  # type: ignore[union-attr]
            ]
            use_composite = len(resolved_markers) > 1

        await ctx.redis_pool.enqueue_job(
            "run_trajectory_analysis",
            job_id            = job_id,
            subject_id        = input.subject_id,
            marker_refs       = resolved_markers,
            use_composite     = use_composite,
            timeframe         = timeframe_dict,
            trajectory_params = trajectory_params_dict,
            db_path           = ctx.db_path,
            rawdata_root      = ctx.rawdata_root,
            reports_root      = ctx.reports_root,
            created_at        = created_at,
            _job_id           = job_id,
        )

        return AnalysisJob(
            job_id        = job_id,
            status        = JobStatus.PENDING,
            progress      = None,
            created_at    = created_at,
            result        = None,
            error_message = None,
        )

    # ── 2. Subject CRUD ────────────────────────────────────────────────────────

    @strawberry.mutation(description="Create a new subject. subject_id is auto-generated.")
    def create_subject(
        self,
        info: strawberry.types.Info[AppContext, None],
        input: SubjectInput,
    ) -> Subject:
        ctx          = info.context
        rawdata_root = ctx.rawdata_root
        db_path      = ctx.db_path

        existing = [
            name for name in os.listdir(rawdata_root)
            if os.path.isdir(os.path.join(rawdata_root, name))
        ] if os.path.isdir(rawdata_root) else []

        max_num = 0
        for name in existing:
            parts = name.split("_")
            if len(parts) == 2 and parts[0] == "subject" and parts[1].isdigit():
                max_num = max(max_num, int(parts[1]))

        subject_id  = f"subject_{str(max_num + 1).zfill(3)}"
        subject_dir = os.path.join(rawdata_root, subject_id)
        os.makedirs(subject_dir, exist_ok=True)

        created_at = datetime.now(timezone.utc).isoformat()
        profile = {
            "subject_id": subject_id,
            "first_name": input.first_name,
            "last_name":  input.last_name,
            "sex":        input.sex,
            "dob":        input.dob,
            "email":      input.email,
            "phone":      input.phone,
            "notes":      input.notes,
            "created_at": created_at,
        }
        with open(os.path.join(subject_dir, "profile.json"), "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO subjects (subject_id, first_name, last_name, sex, dob, "
                "email, phone, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (subject_id, input.first_name, input.last_name, input.sex, input.dob,
                 input.email, input.phone, input.notes, created_at),
            )
            conn.commit()

        return Subject(
            subject_id = subject_id,
            first_name = input.first_name,
            last_name  = input.last_name,
            sex        = input.sex,
            dob        = input.dob,
            email      = input.email,
            phone      = input.phone,
            notes      = input.notes,
            created_at = created_at,
        )

    @strawberry.mutation(description="Update an existing subject's profile.")
    def update_subject(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
        input: SubjectInput,
    ) -> Subject:
        ctx          = info.context
        rawdata_root = ctx.rawdata_root
        db_path      = ctx.db_path

        profile_path = os.path.join(rawdata_root, subject_id, "profile.json")
        if not os.path.isfile(profile_path):
            raise GraphQLError(f"Subject '{subject_id}' not found.")

        with open(profile_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        created_at = existing.get("created_at", "")

        profile = {
            "subject_id": subject_id,
            "first_name": input.first_name,
            "last_name":  input.last_name,
            "sex":        input.sex,
            "dob":        input.dob,
            "email":      input.email,
            "phone":      input.phone,
            "notes":      input.notes,
            "created_at": created_at,
        }
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        with get_connection(db_path) as conn:
            conn.execute(
                "UPDATE subjects SET first_name=?, last_name=?, sex=?, dob=?, "
                "email=?, phone=?, notes=? WHERE subject_id=?",
                (input.first_name, input.last_name, input.sex, input.dob,
                 input.email, input.phone, input.notes, subject_id),
            )
            conn.commit()

        return Subject(
            subject_id = subject_id,
            first_name = input.first_name,
            last_name  = input.last_name,
            sex        = input.sex,
            dob        = input.dob,
            email      = input.email,
            phone      = input.phone,
            notes      = input.notes,
            created_at = created_at,
        )

    @strawberry.mutation(
        description="Soft-delete a subject: moves directory to data/deleted_subjects/."
    )
    def delete_subject(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
    ) -> bool:
        ctx          = info.context
        rawdata_root = ctx.rawdata_root
        db_path      = ctx.db_path

        subject_dir = os.path.join(rawdata_root, subject_id)
        if not os.path.isdir(subject_dir):
            raise GraphQLError(f"Subject '{subject_id}' not found.")

        deleted_root = os.path.join(os.path.dirname(rawdata_root), "deleted_subjects")
        os.makedirs(deleted_root, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        shutil.move(subject_dir, os.path.join(deleted_root, f"{subject_id}_{timestamp}"))

        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
            conn.commit()

        return True

    # ── 3. Module CRUD ─────────────────────────────────────────────────────────

    @strawberry.mutation(description="Create a new module.")
    def create_module(
        self,
        info: strawberry.types.Info[AppContext, None],
        input: ModuleInput,
    ) -> Module:
        ctx     = info.context
        path    = ctx.modules_path
        modules = ctx.modules

        if any(m["module_id"] == input.module_id for m in modules["modules"]):
            raise GraphQLError(f"module_id '{input.module_id}' already exists.")

        new_mod = {
            "module_id":   input.module_id,
            "module_name": input.module_name,
            "description": input.description,
            "format":      input.format,
            "markers":     [],
        }
        modules["modules"].append(new_mod)
        _write_modules(path, modules)
        info.context.request.app.state.modules = modules

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "INSERT INTO modules (module_id, module_name, description, format) "
                "VALUES (?, ?, ?, ?)",
                (input.module_id, input.module_name, input.description, input.format),
            )
            conn.commit()

        return Module.from_dict(new_mod)

    @strawberry.mutation(description="Update an existing module's name and description.")
    def update_module(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        input: ModuleUpdateInput,
    ) -> Module:
        ctx     = info.context
        path    = ctx.modules_path
        modules = ctx.modules

        mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
        if mod is None:
            raise GraphQLError(f"Module '{module_id}' not found.")

        mod["module_name"] = input.module_name
        mod["description"] = input.description
        _write_modules(path, modules)
        info.context.request.app.state.modules = modules

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "UPDATE modules SET module_name=?, description=? WHERE module_id=?",
                (input.module_name, input.description, module_id),
            )
            conn.commit()

        return Module.from_dict(mod)

    @strawberry.mutation(
        description=(
            "Delete a module and archive its reference range files to "
            "data/deleted_reference_ranges/."
        )
    )
    def delete_module(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
    ) -> bool:
        ctx     = info.context
        path    = ctx.modules_path
        modules = ctx.modules

        before = len(modules["modules"])
        modules["modules"] = [m for m in modules["modules"] if m["module_id"] != module_id]
        if len(modules["modules"]) == before:
            raise GraphQLError(f"Module '{module_id}' not found.")

        _write_modules(path, modules)
        info.context.request.app.state.modules = modules

        ref_module_dir = os.path.join(ctx.references_root, module_id)
        if os.path.isdir(ref_module_dir):
            deleted_refs = os.path.join(os.path.dirname(ctx.references_root), "deleted_reference_ranges")
            os.makedirs(deleted_refs, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            shutil.move(ref_module_dir, os.path.join(deleted_refs, f"{module_id}_{ts}"))

        with get_connection(ctx.db_path) as conn:
            conn.execute("DELETE FROM markers WHERE module_id=?", (module_id,))
            conn.execute("DELETE FROM modules WHERE module_id=?", (module_id,))
            conn.execute("DELETE FROM zone_references WHERE module_id=?", (module_id,))
            conn.commit()

        return True

    # ── 4. Marker CRUD ─────────────────────────────────────────────────────────

    @strawberry.mutation(description="Add a marker to an existing module.")
    def create_marker(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        input: MarkerInput,
    ) -> Marker:
        ctx     = info.context
        path    = ctx.modules_path
        modules = ctx.modules

        mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
        if mod is None:
            raise GraphQLError(f"Module '{module_id}' not found.")
        if any(mk["marker_id"] == input.marker_id for mk in mod["markers"]):
            raise GraphQLError(f"marker_id '{input.marker_id}' already exists in this module.")

        new_marker = {
            "marker_id":        input.marker_id,
            "marker_name":      input.marker_name,
            "description":      input.description,
            "unit":             input.unit,
            "volatility_class": input.volatility_class,
        }
        mod["markers"].append(new_marker)
        _write_modules(path, modules)
        info.context.request.app.state.modules = modules

        # Write initial reference range JSON
        ref_dir  = os.path.join(ctx.references_root, module_id)
        os.makedirs(ref_dir, exist_ok=True)
        ref_data = {
            "module_id": module_id,
            "marker_id": input.marker_id,
            "generic": {
                "healthy_min":          input.healthy_min,
                "healthy_max":          input.healthy_max,
                "vulnerability_margin": input.vulnerability_margin,
            },
        }
        with open(os.path.join(ref_dir, f"{input.marker_id}.json"), "w", encoding="utf-8") as f:
            json.dump(ref_data, f, indent=2)

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO zone_references "
                "(module_id, marker_id, sex, age, healthy_min, healthy_max, vulnerability_margin) "
                "VALUES (?, ?, NULL, NULL, ?, ?, ?)",
                (module_id, input.marker_id, input.healthy_min, input.healthy_max, input.vulnerability_margin),
            )
            conn.execute(
                "INSERT INTO markers (module_id, marker_id, marker_name, description, unit, volatility_class) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(module_id, marker_id) DO UPDATE SET "
                "marker_name=excluded.marker_name, description=excluded.description, "
                "unit=excluded.unit, volatility_class=excluded.volatility_class",
                (module_id, input.marker_id, input.marker_name, input.description,
                 input.unit, input.volatility_class),
            )
            conn.commit()

        return Marker.from_dict(new_marker)

    @strawberry.mutation(description="Update an existing marker's metadata.")
    def update_marker(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        marker_id: str,
        input: MarkerUpdateInput,
    ) -> Marker:
        ctx     = info.context
        path    = ctx.modules_path
        modules = ctx.modules

        mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
        if mod is None:
            raise GraphQLError(f"Module '{module_id}' not found.")
        mk = next((mk for mk in mod["markers"] if mk["marker_id"] == marker_id), None)
        if mk is None:
            raise GraphQLError(f"Marker '{marker_id}' not found in module '{module_id}'.")

        mk["marker_name"]      = input.marker_name
        mk["description"]      = input.description
        mk["unit"]             = input.unit
        mk["volatility_class"] = input.volatility_class
        _write_modules(path, modules)
        info.context.request.app.state.modules = modules

        ref_path = os.path.join(ctx.references_root, module_id, f"{marker_id}.json")
        if os.path.isfile(ref_path):
            ref_data = _read_ref_json(ref_path)
        else:
            ref_data = {"module_id": module_id, "marker_id": marker_id}
        ref_data["generic"] = {
            "healthy_min":          input.healthy_min,
            "healthy_max":          input.healthy_max,
            "vulnerability_margin": input.vulnerability_margin,
        }
        os.makedirs(os.path.dirname(ref_path), exist_ok=True)
        _write_ref_json(ref_path, ref_data)

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO zone_references "
                "(module_id, marker_id, sex, age, healthy_min, healthy_max, vulnerability_margin) "
                "VALUES (?, ?, NULL, NULL, ?, ?, ?)",
                (module_id, marker_id, input.healthy_min, input.healthy_max, input.vulnerability_margin),
            )
            conn.execute(
                "UPDATE markers SET marker_name=?, description=?, unit=?, volatility_class=? "
                "WHERE module_id=? AND marker_id=?",
                (input.marker_name, input.description, input.unit, input.volatility_class,
                 module_id, marker_id),
            )
            conn.commit()

        return Marker.from_dict(mk)

    @strawberry.mutation(
        description=(
            "Delete a marker and archive its reference range JSON to "
            "data/deleted_reference_ranges/{module_id}/."
        )
    )
    def delete_marker(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        marker_id: str,
    ) -> bool:
        ctx     = info.context
        path    = ctx.modules_path
        modules = ctx.modules

        mod = next((m for m in modules["modules"] if m["module_id"] == module_id), None)
        if mod is None:
            raise GraphQLError(f"Module '{module_id}' not found.")

        before = len(mod["markers"])
        mod["markers"] = [mk for mk in mod["markers"] if mk["marker_id"] != marker_id]
        if len(mod["markers"]) == before:
            raise GraphQLError(f"Marker '{marker_id}' not found.")

        _write_modules(path, modules)
        info.context.request.app.state.modules = modules

        ref_path = os.path.join(ctx.references_root, module_id, f"{marker_id}.json")
        if os.path.isfile(ref_path):
            deleted_refs = os.path.join(
                os.path.dirname(ctx.references_root), "deleted_reference_ranges", module_id
            )
            os.makedirs(deleted_refs, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            shutil.move(ref_path, os.path.join(deleted_refs, f"{marker_id}_{ts}.json"))

        with get_connection(ctx.db_path) as conn:
            conn.execute("DELETE FROM markers WHERE module_id=? AND marker_id=?", (module_id, marker_id))
            conn.execute(
                "DELETE FROM zone_references "
                "WHERE module_id=? AND marker_id=? AND sex IS NULL AND age IS NULL",
                (module_id, marker_id),
            )
            conn.commit()

        return True

    # ── 5. Datapoint CRUD ──────────────────────────────────────────────────────

    @strawberry.mutation(description="Add a datapoint to a subject's marker dataset.")
    def add_datapoint(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
        module_id:  str,
        marker_id:  str,
        input: DatapointInput,
    ) -> Datapoint:
        ctx        = info.context
        marker_dir = os.path.join(ctx.rawdata_root, subject_id, module_id, marker_id)
        os.makedirs(marker_dir, exist_ok=True)
        index_path = os.path.join(marker_dir, "index.json")

        if os.path.isfile(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = {
                "subject_id": subject_id,
                "module_id":  module_id,
                "marker_id":  marker_id,
                "entries":    [],
            }

        safe_ts  = input.measured_at.replace(":", "-").replace("+", "").rstrip("Z") + "Z"
        filename = f"{safe_ts}.json"

        if any(e["file"] == filename for e in index["entries"]):
            raise GraphQLError("A datapoint with this timestamp already exists.")

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        dp = {
            "schema_version": "1.0",
            "module_id":      module_id,
            "marker_id":      marker_id,
            "subject_id":     subject_id,
            "measured_at":    input.measured_at,
            "value":          input.value,
            "unit":           input.unit,
            "data_quality":   input.data_quality,
            "created_at":     created_at,
        }
        with open(os.path.join(marker_dir, filename), "w", encoding="utf-8") as f:
            json.dump(dp, f, indent=2)

        index["entries"].append({"measured_at": input.measured_at, "file": filename})
        index["entries"].sort(key=lambda e: e["measured_at"])
        _save_index(index_path, index)

        table = _datapoint_table(subject_id, module_id, marker_id)
        with get_connection(ctx.db_path) as conn:
            _ensure_datapoint_table(conn, table)
            conn.execute(
                f'INSERT INTO "{table}" (measured_at, value, unit, data_quality, created_at) '
                f'VALUES (?, ?, ?, ?, ?) ON CONFLICT(measured_at) DO UPDATE SET '
                f'value=excluded.value, unit=excluded.unit, data_quality=excluded.data_quality',
                (input.measured_at, input.value, input.unit, input.data_quality, created_at),
            )
            conn.commit()

        return Datapoint(
            measured_at  = input.measured_at,
            value        = input.value,
            unit         = input.unit,
            data_quality = input.data_quality,
        )

    @strawberry.mutation(
        description=(
            "Upload a JSON file to add a datapoint. The file must contain "
            "measured_at (ISO 8601), value (number), and unit fields."
        )
    )
    async def upload_datapoint(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
        module_id:  str,
        marker_id:  str,
        file: Upload,
    ) -> Datapoint:
        ctx        = info.context
        marker_dir = os.path.join(ctx.rawdata_root, subject_id, module_id, marker_id)
        os.makedirs(marker_dir, exist_ok=True)
        index_path = os.path.join(marker_dir, "index.json")

        content = await file.read()
        try:
            dp = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GraphQLError("Uploaded file is not valid JSON.")

        for key in ("measured_at", "value", "unit"):
            if key not in dp:
                raise GraphQLError(f"Missing required field: {key}")

        if os.path.isfile(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = {
                "subject_id": subject_id,
                "module_id":  module_id,
                "marker_id":  marker_id,
                "entries":    [],
            }

        safe_ts  = dp["measured_at"].replace(":", "-").replace("+", "").rstrip("Z") + "Z"
        filename = f"{safe_ts}.json"

        if any(e["file"] == filename for e in index["entries"]):
            raise GraphQLError("A datapoint with this timestamp already exists.")

        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with open(os.path.join(marker_dir, filename), "wb") as f:
            f.write(content)

        index["entries"].append({"measured_at": dp["measured_at"], "file": filename})
        index["entries"].sort(key=lambda e: e["measured_at"])
        _save_index(index_path, index)

        table = _datapoint_table(subject_id, module_id, marker_id)
        with get_connection(ctx.db_path) as conn:
            _ensure_datapoint_table(conn, table)
            conn.execute(
                f'INSERT INTO "{table}" (measured_at, value, unit, data_quality, created_at) '
                f'VALUES (?, ?, ?, ?, ?) ON CONFLICT(measured_at) DO UPDATE SET '
                f'value=excluded.value, unit=excluded.unit, data_quality=excluded.data_quality',
                (dp["measured_at"], dp["value"], dp.get("unit"), dp.get("data_quality", "good"), created_at),
            )
            conn.commit()

        return Datapoint(
            measured_at  = dp["measured_at"],
            value        = float(dp["value"]),
            unit         = dp.get("unit", ""),
            data_quality = dp.get("data_quality", "good"),
        )

    @strawberry.mutation(description="Update an existing datapoint (identified by its original measured_at timestamp).")
    def update_datapoint(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id:          str,
        module_id:           str,
        marker_id:           str,
        original_measured_at: str,
        input: DatapointInput,
    ) -> Datapoint:
        ctx        = info.context
        marker_dir = os.path.join(ctx.rawdata_root, subject_id, module_id, marker_id)
        index_path = os.path.join(marker_dir, "index.json")

        if not os.path.isfile(index_path):
            raise GraphQLError("Dataset not found.")

        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        entry = next((e for e in index["entries"] if e["measured_at"] == original_measured_at), None)
        if entry is None:
            raise GraphQLError("Datapoint not found.")

        new_safe_ts  = input.measured_at.replace(":", "-").replace("+", "").rstrip("Z") + "Z"
        new_filename = f"{new_safe_ts}.json"

        if input.measured_at != original_measured_at:
            if any(e["file"] == new_filename for e in index["entries"]):
                raise GraphQLError("A datapoint with the new timestamp already exists.")

        old_file_path = os.path.join(marker_dir, entry["file"])
        with open(old_file_path, "r", encoding="utf-8") as f:
            existing_dp = json.load(f)

        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new_dp = {
            **existing_dp,
            "measured_at":  input.measured_at,
            "value":        input.value,
            "unit":         input.unit,
            "data_quality": input.data_quality,
            "updated_at":   updated_at,
        }
        new_file_path = os.path.join(marker_dir, new_filename)
        with open(new_file_path, "w", encoding="utf-8") as f:
            json.dump(new_dp, f, indent=2)
        if new_filename != entry["file"]:
            os.remove(old_file_path)

        for e in index["entries"]:
            if e["measured_at"] == original_measured_at:
                e["measured_at"] = input.measured_at
                e["file"]        = new_filename
                break
        index["entries"].sort(key=lambda e: e["measured_at"])
        _save_index(index_path, index)

        table = _datapoint_table(subject_id, module_id, marker_id)
        with get_connection(ctx.db_path) as conn:
            _ensure_datapoint_table(conn, table)
            conn.execute(
                f'UPDATE "{table}" SET measured_at=?, value=?, unit=?, data_quality=? '
                f'WHERE measured_at=?',
                (input.measured_at, input.value, input.unit, input.data_quality, original_measured_at),
            )
            conn.commit()

        return Datapoint(
            measured_at  = input.measured_at,
            value        = input.value,
            unit         = input.unit,
            data_quality = input.data_quality,
        )

    @strawberry.mutation(
        description="Soft-delete a single datapoint; moves the file to data/deleted_datapoints/."
    )
    def delete_datapoint(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id:  str,
        module_id:   str,
        marker_id:   str,
        measured_at: str,
    ) -> bool:
        ctx        = info.context
        marker_dir = os.path.join(ctx.rawdata_root, subject_id, module_id, marker_id)
        index_path = os.path.join(marker_dir, "index.json")

        if not os.path.isfile(index_path):
            raise GraphQLError("Dataset not found.")

        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        entry = next((e for e in index["entries"] if e["measured_at"] == measured_at), None)
        if entry is None:
            raise GraphQLError("Datapoint not found.")

        file_path = os.path.join(marker_dir, entry["file"])
        if os.path.isfile(file_path):
            silo = os.path.join(
                os.path.dirname(ctx.rawdata_root),
                "deleted_datapoints", subject_id, module_id, marker_id,
            )
            os.makedirs(silo, exist_ok=True)
            ts        = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            silo_name = entry["file"].replace(".json", f"_{ts}.json")
            shutil.move(file_path, os.path.join(silo, silo_name))

        index["entries"] = [e for e in index["entries"] if e["measured_at"] != measured_at]
        _save_index(index_path, index)

        table = _datapoint_table(subject_id, module_id, marker_id)
        with get_connection(ctx.db_path) as conn:
            conn.execute(f'DELETE FROM "{table}" WHERE measured_at=?', (measured_at,))
            conn.commit()

        return True

    @strawberry.mutation(
        description="Soft-delete an entire marker dataset; moves the folder to data/deleted_datasets/."
    )
    def delete_dataset(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
        module_id:  str,
        marker_id:  str,
    ) -> bool:
        ctx        = info.context
        marker_dir = os.path.join(ctx.rawdata_root, subject_id, module_id, marker_id)

        if not os.path.isdir(marker_dir):
            raise GraphQLError("Dataset not found.")

        silo = os.path.join(
            os.path.dirname(ctx.rawdata_root),
            "deleted_datasets", subject_id, module_id,
        )
        os.makedirs(silo, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        shutil.move(marker_dir, os.path.join(silo, f"{marker_id}_{ts}"))

        table = _datapoint_table(subject_id, module_id, marker_id)
        with get_connection(ctx.db_path) as conn:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
            conn.commit()

        return True

    # ── 6. Zone reference CRUD ─────────────────────────────────────────────────

    @strawberry.mutation(description="Add a sex/age-specific demographic zone row for a marker.")
    def add_demographic_zone(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        marker_id: str,
        input: DemographicZoneInput,
    ) -> DemographicZone:
        ctx = info.context

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO zone_references "
                "(module_id, marker_id, sex, age, healthy_min, healthy_max, vulnerability_margin) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (module_id, marker_id, input.sex, input.age,
                 input.healthy_min, input.healthy_max, input.vulnerability_margin),
            )
            conn.commit()

        ref_path = os.path.join(ctx.references_root, module_id, f"{marker_id}.json")
        if os.path.isfile(ref_path):
            ref_data = _read_ref_json(ref_path)
        else:
            ref_data = {"module_id": module_id, "marker_id": marker_id}

        by_sex = ref_data.setdefault("by_sex", {})
        sex_entry = by_sex.setdefault(input.sex, {})
        by_age = sex_entry.setdefault("by_age", {})
        by_age[str(input.age)] = {
            "healthy_min":          input.healthy_min,
            "healthy_max":          input.healthy_max,
            "vulnerability_margin": input.vulnerability_margin,
        }
        _write_ref_json(ref_path, ref_data)

        return DemographicZone(
            sex                  = input.sex,
            age                  = input.age,
            healthy_min          = input.healthy_min,
            healthy_max          = input.healthy_max,
            vulnerability_margin = input.vulnerability_margin,
        )

    @strawberry.mutation(description="Update an existing demographic zone row.")
    def update_demographic_zone(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        marker_id: str,
        sex:       str,
        age:       int,
        input: ZoneBoundaryInput,
    ) -> DemographicZone:
        ctx = info.context

        with get_connection(ctx.db_path) as conn:
            cur = conn.execute(
                "UPDATE zone_references SET healthy_min=?, healthy_max=?, vulnerability_margin=? "
                "WHERE module_id=? AND marker_id=? AND sex=? AND age=?",
                (input.healthy_min, input.healthy_max, input.vulnerability_margin,
                 module_id, marker_id, sex, age),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise GraphQLError("Demographic zone row not found.")

        ref_path = os.path.join(ctx.references_root, module_id, f"{marker_id}.json")
        if os.path.isfile(ref_path):
            ref_data = _read_ref_json(ref_path)
            ref_data.setdefault("by_sex", {}).setdefault(sex, {}).setdefault("by_age", {})[str(age)] = {
                "healthy_min":          input.healthy_min,
                "healthy_max":          input.healthy_max,
                "vulnerability_margin": input.vulnerability_margin,
            }
            _write_ref_json(ref_path, ref_data)

        return DemographicZone(
            sex                  = sex,
            age                  = age,
            healthy_min          = input.healthy_min,
            healthy_max          = input.healthy_max,
            vulnerability_margin = input.vulnerability_margin,
        )

    # ── 7. Markerset CRUD ──────────────────────────────────────────────────────

    @strawberry.mutation(description="Create a new markerset template.")
    def create_markerset_template(
        self,
        info:  strawberry.types.Info[AppContext, None],
        input: CreateMarkersetTemplateInput,
    ) -> MarkersetTemplate:
        ctx          = info.context
        markerset_id = str(uuid4())
        created_at   = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        markers_list = [feature_config_input_to_dict(m) for m in input.markers]
        markers_json = json.dumps(markers_list)

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "INSERT INTO markerset_templates (markerset_id, name, description, markers_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (markerset_id, input.name, input.description, markers_json, created_at),
            )
            conn.commit()

        return MarkersetTemplate(
            markerset_id = markerset_id,
            name         = input.name,
            description  = input.description or "",
            markers      = [feature_config_from_dict(m) for m in markers_list],
            created_at   = created_at,
        )

    @strawberry.mutation(description="Update an existing markerset template.")
    def update_markerset_template(
        self,
        info:         strawberry.types.Info[AppContext, None],
        markerset_id: str,
        input:        CreateMarkersetTemplateInput,
    ) -> MarkersetTemplate:
        ctx          = info.context
        markers_list = [feature_config_input_to_dict(m) for m in input.markers]
        markers_json = json.dumps(markers_list)

        with get_connection(ctx.db_path) as conn:
            cur = conn.execute(
                "UPDATE markerset_templates SET name=?, description=?, markers_json=? "
                "WHERE markerset_id=?",
                (input.name, input.description, markers_json, markerset_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise GraphQLError(f"Markerset template '{markerset_id}' not found.")

            row = conn.execute(
                "SELECT created_at FROM markerset_templates WHERE markerset_id=?",
                (markerset_id,),
            ).fetchone()

        return MarkersetTemplate(
            markerset_id = markerset_id,
            name         = input.name,
            description  = input.description or "",
            markers      = [feature_config_from_dict(m) for m in markers_list],
            created_at   = row["created_at"],
        )

    @strawberry.mutation(description="Delete a markerset template.")
    def delete_markerset_template(
        self,
        info:         strawberry.types.Info[AppContext, None],
        markerset_id: str,
    ) -> bool:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM markerset_templates WHERE markerset_id=?", (markerset_id,)
            )
            conn.commit()
            if cur.rowcount == 0:
                raise GraphQLError(f"Markerset template '{markerset_id}' not found.")
        return True

    @strawberry.mutation(description="Create a markerset instance for a subject.")
    def create_markerset_instance(
        self,
        info:       strawberry.types.Info[AppContext, None],
        subject_id: str,
        input:      CreateMarkersetInstanceInput,
    ) -> MarkersetInstance:
        ctx         = info.context
        instance_id = str(uuid4())
        created_at  = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # For template-based instances, store the full marker list as overrides
        # (sparse override semantics applied at read time by markerset_reader)
        markers_list  = [feature_config_input_to_dict(m) for m in input.markers]
        overrides_json = json.dumps(markers_list)

        with get_connection(ctx.db_path) as conn:
            conn.execute(
                "INSERT INTO markerset_instances "
                "(instance_id, subject_id, markerset_id, name, overrides_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (instance_id, subject_id, input.markerset_id, input.name,
                 overrides_json, created_at),
            )
            conn.commit()

        return MarkersetInstance(
            instance_id  = instance_id,
            subject_id   = subject_id,
            markerset_id = input.markerset_id,
            name         = input.name,
            markers      = [feature_config_from_dict(m) for m in markers_list],
            created_at   = created_at,
        )

    @strawberry.mutation(description="Update a markerset instance.")
    def update_markerset_instance(
        self,
        info:        strawberry.types.Info[AppContext, None],
        instance_id: str,
        input:       CreateMarkersetInstanceInput,
    ) -> MarkersetInstance:
        ctx           = info.context
        markers_list  = [feature_config_input_to_dict(m) for m in input.markers]
        overrides_json = json.dumps(markers_list)

        with get_connection(ctx.db_path) as conn:
            cur = conn.execute(
                "UPDATE markerset_instances SET name=?, markerset_id=?, overrides_json=? "
                "WHERE instance_id=?",
                (input.name, input.markerset_id, overrides_json, instance_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise GraphQLError(f"Markerset instance '{instance_id}' not found.")

            row = conn.execute(
                "SELECT subject_id, created_at FROM markerset_instances WHERE instance_id=?",
                (instance_id,),
            ).fetchone()

        return MarkersetInstance(
            instance_id  = instance_id,
            subject_id   = row["subject_id"],
            markerset_id = input.markerset_id,
            name         = input.name,
            markers      = [feature_config_from_dict(m) for m in markers_list],
            created_at   = row["created_at"],
        )

    @strawberry.mutation(description="Delete a markerset instance.")
    def delete_markerset_instance(
        self,
        info:        strawberry.types.Info[AppContext, None],
        instance_id: str,
    ) -> bool:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM markerset_instances WHERE instance_id=?", (instance_id,)
            )
            conn.commit()
            if cur.rowcount == 0:
                raise GraphQLError(f"Markerset instance '{instance_id}' not found.")
        return True

    @strawberry.mutation(description="Delete a demographic zone row.")
    def delete_demographic_zone(
        self,
        info: strawberry.types.Info[AppContext, None],
        module_id: str,
        marker_id: str,
        sex:       str,
        age:       int,
    ) -> bool:
        ctx = info.context

        with get_connection(ctx.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM zone_references "
                "WHERE module_id=? AND marker_id=? AND sex=? AND age=?",
                (module_id, marker_id, sex, age),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise GraphQLError("Demographic zone row not found.")

        ref_path = os.path.join(ctx.references_root, module_id, f"{marker_id}.json")
        if os.path.isfile(ref_path):
            ref_data = _read_ref_json(ref_path)
            by_sex   = ref_data.get("by_sex", {})
            sex_entry = by_sex.get(sex, {})
            by_age   = sex_entry.get("by_age", {})
            by_age.pop(str(age), None)
            if not by_age:
                sex_entry.pop("by_age", None)
            if not sex_entry:
                by_sex.pop(sex, None)
            if not by_sex:
                ref_data.pop("by_sex", None)
            _write_ref_json(ref_path, ref_data)

        return True
