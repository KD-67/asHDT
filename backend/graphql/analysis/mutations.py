from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

import strawberry
from strawberry.exceptions import GraphQLError

from backend.graphql.context import AppContext
from backend.graphql.analysis.types import (
    AnalysisInput,
    AnalysisJob,
    JobStatus,
)
from backend.core.storage.markerset_reader import resolve_markerset_markers


@strawberry.type
class AnalysisMutations:

    @strawberry.mutation(
        description=(
            "Enqueue an analysis computation and return immediately with a job_id. "
            "Open a jobStatus subscription with that id to receive real-time progress "
            "and the final result."
        )
    )
    async def submit_analysis(
        self,
        info: strawberry.types.Info[AppContext, None],
        input: AnalysisInput,
    ) -> AnalysisJob:
        ctx = info.context

        if ctx.redis_pool is None:
            raise GraphQLError(
                "Redis is not available. Start Redis and restart the server to enable "
                "async analysis jobs."
            )

        # Validate: exactly one of markerset_id / marker_refs must be set
        has_markerset = input.markerset_id is not None
        has_refs      = input.marker_refs  is not None and len(input.marker_refs) > 0
        if has_markerset == has_refs:
            raise GraphQLError(
                "Exactly one of markerset_id or marker_refs must be provided."
            )

        if input.trajectory_params is None:
            raise GraphQLError("trajectory_params is required.")

        job_id     = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        timeframe_dict: dict = {
            "start_time": input.timeframe.start_time,
            "end_time":   input.timeframe.end_time,
        }
        params = input.trajectory_params
        trajectory_params_dict: dict = {
            "polynomial_degree":    params.polynomial_degree,
            "healthy_min":          params.healthy_min,
            "healthy_max":          params.healthy_max,
            "vulnerability_margin": params.vulnerability_margin,
        }

        if has_markerset:
            # Resolve markerset instance → fully-configured markers with DB zone boundaries
            try:
                resolved_markers = resolve_markerset_markers(
                    ctx.db_path, input.subject_id, instance_id=input.markerset_id
                )
            except ValueError as e:
                raise GraphQLError(str(e))
            use_composite = True
        else:
            # Ad-hoc marker_refs
            resolved_markers = [
                {"module_id": m.module_id, "marker_id": m.marker_id}
                for m in input.marker_refs  # type: ignore[union-attr]
            ]
            use_composite = len(resolved_markers) > 1

        await ctx.redis_pool.enqueue_job(
            "run_trajectory_analysis",
            job_id            = job_id,
            subject_id        = input.subject_id,
            marker_refs       = resolved_markers,
            use_composite     = use_composite,
            timeframe         = timeframe_dict,
            trajectory_params = trajectory_params_dict,
            db_path           = ctx.db_path,
            rawdata_root      = ctx.rawdata_root,
            reports_root      = ctx.reports_root,
            created_at        = created_at,
            _job_id           = job_id,
        )

        return AnalysisJob(
            job_id        = job_id,
            status        = JobStatus.PENDING,
            progress      = None,
            created_at    = created_at,
            result        = None,
            error_message = None,
        )
