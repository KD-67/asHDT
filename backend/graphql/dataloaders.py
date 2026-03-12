# DataLoaders prevent the N+1 query problem by batching multiple individual lookups
# into a single database query per request.
#
# Usage in resolvers:
#   subjects = await info.context.subject_loader.load_many(subject_ids)
#
# Each DataLoader is instantiated per-request (in AppContext) so batching is scoped
# to a single request — never leaks data between requests.

from __future__ import annotations
from typing import Optional
from strawberry.dataloader import DataLoader
from backend.startup.database_logistics import get_connection
from backend.graphql.subjects.types import Subject
from backend.graphql.modules.types import Marker


# ── Subject loader ─────────────────────────────────────────────────────────────

def make_subject_loader(db_path: str) -> DataLoader:
    """Batch-loads Subject objects by subject_id."""

    async def load_subjects(subject_ids: list[str]) -> list[Optional[Subject]]:
        if not subject_ids:
            return []
        placeholders = ",".join("?" * len(subject_ids))
        with get_connection(db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM subjects WHERE subject_id IN ({placeholders})",
                list(subject_ids),
            ).fetchall()
        row_map = {r["subject_id"]: Subject.from_row(dict(r)) for r in rows}
        return [row_map.get(sid) for sid in subject_ids]

    return DataLoader(load_fn=load_subjects)


# ── Marker loader ──────────────────────────────────────────────────────────────

def make_marker_loader(db_path: str) -> DataLoader:
    """Batch-loads Marker lists by module_id."""

    async def load_markers(module_ids: list[str]) -> list[list[Marker]]:
        if not module_ids:
            return [[] for _ in module_ids]
        placeholders = ",".join("?" * len(module_ids))
        with get_connection(db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM markers WHERE module_id IN ({placeholders}) ORDER BY module_id, marker_id",
                list(module_ids),
            ).fetchall()
        grouped: dict[str, list[Marker]] = {mid: [] for mid in module_ids}
        for row in rows:
            mid = row["module_id"]
            if mid in grouped:
                grouped[mid].append(Marker.from_dict(dict(row)))
        return [grouped[mid] for mid in module_ids]

    return DataLoader(load_fn=load_markers)
