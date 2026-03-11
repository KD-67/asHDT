# This is the file that must be run to start the server. It establishes all the paths to relevant files, makes sure the backend knows what
# port the frontend is running on, connects to the SQLite database, and store some important paths a app.state so they don't have to keep
# being imported every time they're needed.

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.startup.module_loader import load_modules
from backend.startup.database_logistics import init_db, sync_subjects, sync_zone_references, sync_modules, sync_datapoints
from backend.api.routes import router

logger = logging.getLogger(__name__)

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))                           # resolves to: "c:\Users\kevin\proj\asHDT\backend"
REPO_ROOT       = os.path.dirname(BASE_DIR)                                            # resolves to: "c:\Users\kevin\proj\asHDT"
DATA_DIR        = os.path.join(REPO_ROOT, "data")                                      # resolves to: "c:\Users\kevin\proj\asHDT\data"
DB_PATH         = os.path.join(DATA_DIR, "databases", "asHDT.db")                      # resolves to: "c:\Users\kevin\proj\asHDT\data\databases\asHDT.db"
RAWDATA_ROOT    = os.path.join(DATA_DIR, "raw_data")                                   # resolves to: "c:\Users\kevin\proj\asHDT\data\raw_data"
REPORTS_ROOT    = os.path.join(DATA_DIR, "reports")                                    # resolves to: "c:\Users\kevin\proj\asHDT\data\reports"
MODULES_PATH    = os.path.join(BASE_DIR, "startup", "module_list.json")                # resolves to: "c:\Users\kevin\proj\asHDT\backend\startup\module_list.json"
REFERENCES_ROOT = os.path.join(DATA_DIR, "reference_ranges")                           # resolves to: "c:\Users\kevin\proj\asHDT\data\reference_ranges"
REDIS_URL       = os.environ.get("REDIS_URL", "redis://localhost:6379")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST router (existing — kept until Svelte frontend is migrated to GraphQL) ─
app.include_router(router)

# ── GraphQL router ─────────────────────────────────────────────────────────────
# Mounted at /graphql alongside REST. GraphiQL IDE available at /graphql in browser.
# Subscriptions (jobStatus) are served over WebSocket at ws://localhost:8000/graphql.
from strawberry.fastapi import GraphQLRouter
from backend.graphql.schema import schema
from backend.graphql.context import get_context

graphql_router = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_router, prefix="/graphql")


@app.on_event("startup")
async def startup():
    # ── Sync data sources into SQLite ─────────────────────────────────────────
    init_db(DB_PATH)
    sync_subjects(DB_PATH, RAWDATA_ROOT)
    sync_zone_references(DB_PATH, REFERENCES_ROOT)
    sync_modules(DB_PATH, MODULES_PATH)
    sync_datapoints(DB_PATH, RAWDATA_ROOT)

    # ── Store shared paths and state on app.state ──────────────────────────────
    app.state.modules         = load_modules(MODULES_PATH)
    app.state.modules_path    = MODULES_PATH
    app.state.db_path         = DB_PATH
    app.state.rawdata_root    = RAWDATA_ROOT
    app.state.reports_root    = REPORTS_ROOT
    app.state.references_root = REFERENCES_ROOT

    # ── Create ARQ Redis pool for async job dispatch ───────────────────────────
    # Gracefully degrades if Redis is not running: submitAnalysis mutation will
    # raise a helpful GraphQL error rather than crashing the server at startup.
    try:
        from arq.connections import create_pool, RedisSettings
        app.state.redis_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        logger.info("ARQ Redis pool connected at %s", REDIS_URL)
    except Exception as exc:
        app.state.redis_pool = None
        logger.warning(
            "Redis unavailable (%s). submitAnalysis mutation will not work until "
            "Redis is running and the server is restarted.", exc
        )


@app.on_event("shutdown")
async def shutdown():
    if getattr(app.state, "redis_pool", None) is not None:
        await app.state.redis_pool.aclose()
