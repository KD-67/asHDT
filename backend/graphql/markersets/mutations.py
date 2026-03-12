from __future__ import annotations
import json
from datetime import datetime, timezone
from uuid import uuid4

import strawberry
from strawberry.exceptions import GraphQLError

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.markersets.types import (
    MarkersetTemplate, MarkersetInstance,
    CreateMarkersetTemplateInput, CreateMarkersetInstanceInput,
    feature_config_from_dict, feature_config_input_to_dict,
)


@strawberry.type
class MarkersetMutations:

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
