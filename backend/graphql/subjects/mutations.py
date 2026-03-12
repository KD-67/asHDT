from __future__ import annotations
import json
import os
import shutil
from datetime import datetime, timezone

import strawberry
from strawberry.exceptions import GraphQLError

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.subjects.types import Subject, SubjectInput


@strawberry.type
class SubjectMutations:

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
