from __future__ import annotations
import json
import os
from typing import Optional

import strawberry

from backend.startup.database_logistics import get_connection, _datapoint_table
from backend.graphql.context import AppContext
from backend.graphql.datapoints.types import Datapoint, Dataset


@strawberry.type
class DatapointQueries:

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
