from __future__ import annotations

import strawberry

from backend.startup.database_logistics import get_connection
from backend.graphql.context import AppContext
from backend.graphql.analysis.types import AnalysisJob, AnalysisMethodInfo, JobStatus


@strawberry.type
class AnalysisQueries:

    @strawberry.field(description="List all analysis methods from the registry (includes stubs).")
    def analysis_methods(
        self,
        info: strawberry.types.Info[AppContext, None],
    ) -> list[AnalysisMethodInfo]:
        methods_data = info.context.methods.get("methods", [])
        return [
            AnalysisMethodInfo(
                method_id             = m["method_id"],
                method_name           = m["method_name"],
                description           = m.get("description", ""),
                status                = m.get("status", "stub"),
                accepts_single_marker = m.get("accepts_single_marker", False),
                accepts_markerset     = m.get("accepts_markerset", False),
                min_markers           = m.get("min_markers"),
                max_markers           = m.get("max_markers"),
                params_schema         = m.get("params_schema", "none"),
                output_type           = m.get("output_type", ""),
            )
            for m in methods_data
        ]

    @strawberry.field(description="List past analysis report metadata for a subject.")
    def analysis_reports(
        self,
        info: strawberry.types.Info[AppContext, None],
        subject_id: str,
    ) -> list[AnalysisJob]:
        ctx = info.context
        with get_connection(ctx.db_path) as conn:
            rows = conn.execute(
                "SELECT report_id, requested_at FROM timegraph_reports "
                "WHERE subject_id = ? ORDER BY requested_at DESC",
                (subject_id,),
            ).fetchall()
        # Historical reports are always COMPLETED. Full result data is not stored
        # in SQLite — load the report JSON from the filesystem if needed.
        return [
            AnalysisJob(
                job_id        = r["report_id"],
                status        = JobStatus.COMPLETED,
                progress      = 1.0,
                created_at    = r["requested_at"],
                result        = None,
                error_message = None,
            )
            for r in rows
        ]
