from __future__ import annotations
import json
import os
import shutil
from datetime import datetime, timezone

import strawberry
from strawberry.exceptions import GraphQLError

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.modules.types import (
    Module, Marker, DemographicZone,
    ModuleInput, ModuleUpdateInput,
    MarkerInput, MarkerUpdateInput,
    DemographicZoneInput, ZoneBoundaryInput,
)


def _write_modules(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_ref_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_ref_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@strawberry.type
class ModuleMutations:

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
