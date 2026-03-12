from __future__ import annotations
import json
from typing import Optional

import strawberry

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.markersets.types import (
    MarkersetTemplate, MarkersetInstance,
    feature_config_from_dict,
)


@strawberry.type
class MarkersetQueries:

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
