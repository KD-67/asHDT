from __future__ import annotations
import json
import os
import shutil
from datetime import datetime, timezone

import strawberry
from strawberry.exceptions import GraphQLError
from strawberry.file_uploads import Upload

from backend.startup.database_logistics import (
    get_connection,
    _datapoint_table,
    _ensure_datapoint_table,
)
from backend.graphql.context import AppContext
from backend.graphql.datapoints.types import Datapoint, DatapointInput


def _save_index(index_path: str, data: dict) -> None:
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@strawberry.type
class DatapointMutations:

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
