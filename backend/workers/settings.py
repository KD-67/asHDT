# ARQ WorkerSettings — run workers from repo root with:
#   arq backend.workers.settings.WorkerSettings
#
# Workers run in a SEPARATE process from the FastAPI server.
# They have full access to backend.* imports (same PYTHONPATH).

import os
from arq.connections import RedisSettings
from backend.workers.analysis_tasks import run_trajectory_analysis


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


class WorkerSettings:
    functions = [
        run_trajectory_analysis,
    ]

    redis_settings = RedisSettings.from_dsn(REDIS_URL)

    job_timeout = 600  # seconds

    # Max concurrent jobs per worker process
    max_jobs = 4

    # Log job lifecycle events
    on_startup = None
    on_shutdown = None
