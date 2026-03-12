from __future__ import annotations
from datetime import date
from typing import Optional

import strawberry

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.subjects.types import Subject, ZoneReference


@strawberry.type
class SubjectQueries:

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
