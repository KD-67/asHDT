from __future__ import annotations
from typing import Optional
import strawberry


@strawberry.type
class Subject:
    subject_id: str
    first_name: str
    last_name:  str
    sex:        str
    dob:        str
    email:      Optional[str]
    phone:      Optional[str]
    notes:      Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "Subject":
        return cls(
            subject_id = row["subject_id"],
            first_name = row.get("first_name") or "",
            last_name  = row.get("last_name")  or "",
            sex        = row.get("sex")        or "",
            dob        = row.get("dob")        or "",
            email      = row.get("email"),
            phone      = row.get("phone"),
            notes      = row.get("notes"),
            created_at = row.get("created_at") or "",
        )


@strawberry.type
class ZoneReference:
    """Age/sex-interpolated zone boundaries for a given subject + marker."""
    healthy_min:          float
    healthy_max:          float
    vulnerability_margin: float
    note:                 Optional[str]


@strawberry.input
class SubjectInput:
    first_name: str
    last_name:  str
    sex:        str
    dob:        str
    email:      str
    phone:      str
    notes:      str = ""
