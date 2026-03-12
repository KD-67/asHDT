from __future__ import annotations
from typing import Optional

import strawberry

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.modules.types import Module, DemographicZone


@strawberry.type
class ModuleQueries:

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
