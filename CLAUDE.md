# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**asHDT** — a health-data trajectory analysis tool. A FastAPI backend that reads raw biomarker time-series data from the filesystem, fits polynomials to normalized health scores, and classifies each data point into one of 27 discrete trajectory states using zone assignment + two derivatives (f, f', f'').

The backend serves a Svelte 5 frontend located at `frontend/`, expected at `http://localhost:5173`.

## Running the Project

```bash
# Backend — from repo root
uvicorn backend.main:app --reload

# Frontend — from frontend/
npm run dev

# Worker (required for analysis jobs) — from repo root
python -m arq backend.workers.settings.WorkerSettings

# Redis (required for analysis jobs)
docker run -d -p 6379:6379 redis:alpine
```

**Backend dependencies:** FastAPI, uvicorn, numpy, pydantic, strawberry-graphql, arq, redis

## Architecture

### Startup Flow (`backend/main.py`)
1. `init_db()` — creates SQLite database and tables if they don't exist
2. Sync functions — populate SQLite from filesystem: `sync_subjects`, `sync_zone_references`, `sync_modules`, `sync_datapoints`
3. `load_modules()` — reads `backend/startup/module_list.json` into `app.state.modules`
4. ARQ Redis pool — created for async job dispatch; gracefully degrades if Redis is unavailable
5. Paths stored in `app.state`: `db_path`, `rawdata_root`, `reports_root`, `references_root`, `modules_path`

### API — Dual Stack (REST + GraphQL)

Both are mounted simultaneously. The **REST router** (`backend/api/routes.py`) is the original implementation and remains registered. The **GraphQL API** (`/graphql`) is the active API used by the frontend. REST is kept for reference but is no longer called by the frontend.

**GraphQL endpoint:** `POST /graphql` (queries + mutations), `ws://localhost:8000/graphql` (subscriptions)
**GraphiQL IDE:** `http://localhost:8000/graphql` in browser

#### GraphQL Operations
- **Queries:** `subjects`, `subject`, `modules`, `module`, `datasets`, `datapoints`, `demographicZones`, `zoneReference`, `analysisReports`
- **Mutations:** `createSubject`, `updateSubject`, `deleteSubject`, `createModule`, `updateModule`, `deleteModule`, `createMarker`, `updateMarker`, `deleteMarker`, `addDatapoint`, `updateDatapoint`, `deleteDatapoint`, `uploadDatapoint`, `deleteDataset`, `addDemographicZone`, `updateDemographicZone`, `deleteDemographicZone`, `submitAnalysis`
- **Subscriptions:** `jobStatus` — streams real-time analysis progress over WebSocket

#### Analysis Flow
`submitAnalysis` mutation → ARQ enqueues job to Redis → `run_trajectory_analysis` worker executes → publishes progress to Redis pub/sub channel `job:{job_id}` → `jobStatus` subscription streams updates to client → on COMPLETED, client stores result in `localStorage` and opens the report page.

### Data Pipeline (Analysis)
`mutations.py:submitAnalysis` → ARQ → `workers/analysis_tasks.py:run_trajectory_analysis` → `data_reader.read_timeseries()` → `trajectory_computer.compute_trajectory()` → `report_generator.save_timegraph_report()`

- **data_reader** — reads raw JSON files from `data/raw_data/{subject}/{module}/{marker}/`, guided by each marker folder's `index.json`.
- **trajectory_computer** — purely computational, no I/O. Normalizes raw values to a U-shaped health score `h(raw)`, fits a polynomial via `np.polyfit`, evaluates f(x), f'(x), f''(x), assigns zones, and maps to one of 27 trajectory states.
- **report_generator** — dual write: saves full JSON report to `data/reports/{subject}/{report_id}.json` AND inserts metadata row into SQLite.

### Data Layout
```
data/
  raw_data/{subject_id}/{module_id}/{marker_id}/
    index.json              # list of entries with timestamps + filenames
    *.json                  # individual datapoint files
  raw_data/{subject_id}/profile.json
  databases/asHDT.db        # SQLite (gitignored)
  reports/                  # generated report JSONs
  reference_ranges/         # zone boundary JSON files per module/marker
```

### Key Domain Concepts
- **Module** — a test or measurement category (e.g. `fitness`, `vtf_stresstest`)
- **Marker** — a specific measurable within a module (e.g. `vo2max`, `100m_sprint`)
- **Health score h(raw)** — U-shaped normalization: `1 - |raw - mid| / half_range`, where h=1 is optimal center, h=0 is boundary of healthy range, h<0 is outside
- **Trajectory state (1–27)** — combination of zone (3) × f' sign (3) × f'' sign (3)
- **Zone boundaries** — `healthy_min`, `healthy_max`, `vulnerability_margin`

## Frontend (`frontend/`)

Svelte 5 app using runes (`$state`, `$derived`, `$effect`). No external state management or GraphQL client library — raw `fetch` and `WebSocket` via a shared utility.

**GraphQL client:** `frontend/src/lib/gql.js`
- `gql(query, variables)` — queries and mutations
- `gqlUpload(query, variables, fileKey, file)` — file upload mutation (multipart request spec)
- `subscribe(query, variables, onData, onError)` — WebSocket subscription (graphql-transport-ws protocol)

**Components:**
- `request_report_form.svelte` — analysis submission form; uses `submitAnalysis` + `jobStatus` subscription
- `subject_management.svelte` — subject CRUD + inline dataset/datapoint management
- `add_module_page.svelte` — module, marker, and demographic zone reference CRUD
- `dataset_management.svelte` — standalone dataset/datapoint view
- `timegraph_report_page.svelte` — reads report from `localStorage`, renders chart and table
- `timegraph_chart.svelte` / `timegraph_table.svelte` — expect snake_case fields from localStorage

**Important:** The report stored in `localStorage` uses snake_case field names (`health_score`, `f_prime`, `t0_iso`, etc.) to match what `timegraph_chart.svelte` and `timegraph_table.svelte` expect. The GraphQL response (camelCase) is transformed to snake_case in `request_report_form.svelte` before storing.

## GraphQL Schema Files
```
backend/graphql/
  schema.py              # roots: Query, Mutation, Subscription
  context.py             # AppContext — db_path, rawdata_root, redis_pool, etc.
  dataloaders.py         # batch loaders for subjects and markers
  resolvers/
    queries.py
    mutations.py         # includes uploadDatapoint using strawberry Upload scalar
    subscriptions.py     # jobStatus WebSocket subscription
  types/
    subject.py           # Subject, ZoneReference
    module.py            # Module, Marker, DemographicZone
    datapoint.py         # Datapoint, Dataset
    analysis.py          # AnalysisJob, TrajectoryReport, AnalysisResult union, enums

backend/workers/
  analysis_tasks.py      # run_trajectory_analysis ARQ task
  settings.py            # WorkerSettings
```
