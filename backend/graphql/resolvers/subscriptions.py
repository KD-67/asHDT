# jobStatus subscription — streams AnalysisJob updates in real time.
#
# Flow:
#   1. Client calls submitAnalysis mutation → receives job_id (status=PENDING)
#   2. Client immediately opens jobStatus subscription with that job_id
#   3. Worker publishes progress updates to Redis channel "job:{job_id}"
#   4. Subscription resolver forwards each update to the client as an AnalysisJob
#   5. When status=COMPLETED or FAILED the generator closes and the WebSocket disconnects
#
# EDGE CASE NOTE: If the worker completes before the subscription is established,
# the client will miss the pub/sub message. In practice the intended workflow
# (submit → subscribe immediately) avoids this. A future improvement would be to
# check the ARQ job state on entry and yield the result immediately if already done.

from __future__ import annotations
import asyncio
import json
import os
import logging
from typing import AsyncGenerator

import strawberry
import redis.asyncio as aioredis

from backend.graphql.types.analysis import (
    AnalysisJob,
    JobStatus,
    build_trajectory_report,
)

logger = logging.getLogger(__name__)

REDIS_URL    = os.environ.get("REDIS_URL", "redis://localhost:6379")
SUB_TIMEOUT  = 600  # seconds — max time a subscription stays open (10 min)


def _parse_update(job_id: str, data: dict) -> AnalysisJob:
    """Convert a raw worker-published dict into an AnalysisJob GraphQL object."""
    status = JobStatus(data["status"])
    result = None

    if status == JobStatus.COMPLETED and "result" in data:
        try:
            result = build_trajectory_report(data)
        except Exception as exc:
            logger.error("Failed to parse trajectory result for job %s: %s", job_id, exc)

    return AnalysisJob(
        job_id        = job_id,
        status        = status,
        progress      = data.get("progress"),
        created_at    = data.get("created_at", ""),
        result        = result,
        error_message = data.get("error"),
    )


@strawberry.type
class Subscription:

    @strawberry.subscription(
        description=(
            "Stream real-time status updates for an analysis job. "
            "Subscribe immediately after calling submitAnalysis. "
            "The stream closes automatically when status reaches COMPLETED or FAILED."
        )
    )
    async def job_status(
        self,
        info: strawberry.types.Info,
        job_id: str,
    ) -> AsyncGenerator[AnalysisJob, None]:

        # Yield an initial PENDING state so the client has immediate feedback
        yield AnalysisJob(
            job_id        = job_id,
            status        = JobStatus.PENDING,
            progress      = None,
            created_at    = "",
            result        = None,
            error_message = None,
        )

        # Open a dedicated Redis connection for pub/sub.
        # Each subscription needs its own connection because subscribing puts
        # the connection into a mode where only pub/sub commands are allowed.
        conn   = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = conn.pubsub()

        try:
            await pubsub.subscribe(f"job:{job_id}")

            deadline = asyncio.get_event_loop().time() + SUB_TIMEOUT

            async for message in pubsub.listen():
                # Respect timeout
                if asyncio.get_event_loop().time() > deadline:
                    yield AnalysisJob(
                        job_id        = job_id,
                        status        = JobStatus.FAILED,
                        progress      = None,
                        created_at    = "",
                        result        = None,
                        error_message = "Subscription timed out waiting for job completion.",
                    )
                    break

                if message["type"] != "message":
                    continue  # skip subscribe/unsubscribe confirmation messages

                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("Unparseable pub/sub message for job %s: %s", job_id, exc)
                    continue

                update = _parse_update(job_id, data)
                yield update

                # Terminal states — close the stream
                if update.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break

        except Exception as exc:
            logger.error("Subscription error for job %s: %s", job_id, exc)
            yield AnalysisJob(
                job_id        = job_id,
                status        = JobStatus.FAILED,
                progress      = None,
                created_at    = "",
                result        = None,
                error_message = str(exc),
            )
        finally:
            await pubsub.unsubscribe(f"job:{job_id}")
            await conn.aclose()
