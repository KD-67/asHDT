# ARQ WorkerSettings — run workers from repo root with:
#   arq backend.workers.settings.WorkerSettings
#
# Workers run in a SEPARATE process from the FastAPI server.
# They have full access to backend.* imports (same PYTHONPATH).
#
# To add a new analysis method:
#   1. Write the task function in analysis_tasks.py
#   2. Import it here and add it to the `functions` list — that's all.

import os
from arq.connections import RedisSettings
from backend.workers.analysis_tasks import run_trajectory_analysis


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


class WorkerSettings:
    # All registered task functions. Add future ML/PCA/automated tasks here.
    functions = [
        run_trajectory_analysis,
        # run_pca_analysis,          # future
        # run_ml_analysis,           # future
        # run_automated_analysis,    # future
    ]

    redis_settings = RedisSettings.from_dsn(REDIS_URL)

    # How long a job can run before ARQ considers it timed out (seconds)
    job_timeout = 600  # 10 minutes — generous for future heavy ML jobs

    # Max concurrent jobs per worker process
    max_jobs = 4

    # Log job lifecycle events
    on_startup = None
    on_shutdown = None
