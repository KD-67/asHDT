# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**asHDT** — a health-data trajectory analysis tool and digital twin hub. A FastAPI backend that reads raw biomarker time-series data from the filesystem, fits polynomials to normalized health scores, and classifies each data point into one of 27 discrete trajectory states using zone assignment + two derivatives (f, f', f''). Multiple markers can be combined into named **markersets** that feed a growing library of analysis methods driven by a JSON registry.

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
1. `init_db()` — creates SQLite database and tables if they don't exist (including markerset tables)
2. Sync functions — populate SQLite from filesystem: `sync_subjects`, `sync_zone_references`, `sync_modules`, `sync_datapoints`
3. `load_modules()` — reads `backend/startup/module_list.json` into `app.state.modules`
4. `load_analysis_methods()` — reads `backend/startup/analysis_list.json` into `app.state.methods`
5. ARQ Redis pool — created for async job dispatch; gracefully degrades if Redis is unavailable
6. Paths stored in `app.state`: `db_path`, `rawdata_root`, `reports_root`, `references_root`, `modules_path`

### API — GraphQL

**GraphQL endpoint:** `POST /graphql` (queries + mutations), `ws://localhost:8000/graphql` (subscriptions)
**GraphiQL IDE:** `http://localhost:8000/graphql` in browser

The REST router (`backend/api/routes.py`) remains registered but is no longer called by the frontend.

#### GraphQL Operations
- **Queries:** `subjects`, `subject`, `modules`, `module`, `datasets`, `datapoints`, `demographicZones`, `zoneReference`, `analysisReports`, `analysisMethods`, `markersetTemplates`, `markersetTemplate`, `markersetInstances`
- **Mutations:** `createSubject`, `updateSubject`, `deleteSubject`, `createModule`, `updateModule`, `deleteModule`, `createMarker`, `updateMarker`, `deleteMarker`, `addDatapoint`, `updateDatapoint`, `deleteDatapoint`, `uploadDatapoint`, `deleteDataset`, `addDemographicZone`, `updateDemographicZone`, `deleteDemographicZone`, `submitAnalysis`, `createMarkersetTemplate`, `updateMarkersetTemplate`, `deleteMarkersetTemplate`, `createMarkersetInstance`, `updateMarkersetInstance`, `deleteMarkersetInstance`
- **Subscriptions:** `jobStatus` — streams real-time analysis progress over WebSocket

#### Analysis Flow
`submitAnalysis` mutation → resolves markerset or marker_refs → ARQ enqueues job to Redis → worker executes → publishes progress to Redis pub/sub channel `job:{job_id}` → `jobStatus` subscription streams updates to client → on COMPLETED, client stores result in `localStorage` and opens the report page.

### Analysis Method Registry (`analysis_list.json`)
Defines all known methods with `status` ("implemented" | "stub"), `accepts_single_marker`, `accepts_markerset`, `params_schema`, and `output_type`. Loaded at startup into `app.state.methods`. Served via `analysisMethods` query. The frontend method dropdown is built dynamically from this list — stubs appear disabled. To add a new method: add an entry here + write a worker task + wire up in `mutations.py`.

Currently implemented: `trajectory`. Stubs: `pca`, `automated`.

### Data Pipeline — Single Marker
`submitAnalysis(marker_refs=[...])` → `run_trajectory_analysis` (use_composite=False) → `data_reader.read_timeseries()` → `trajectory_computer.compute_trajectory()` → `report_generator.save_timegraph_report()`

### Data Pipeline — Markerset (Multi-Marker Composite)
`submitAnalysis(markerset_id=...)` → `markerset_reader.resolve_markerset_markers()` (merges template + overrides, attaches per-marker zone_boundaries from DB) → `run_trajectory_analysis` (use_composite=True) → `data_reader.read_multi_marker_timeseries()` → `composite_builder.build_composite_timeseries()` → `trajectory_computer.compute_trajectory()` → `report_generator.save_timegraph_report()`

The composite builder applies per-marker feature transforms (log, rolling_avg, normalize, lag), normalises each marker to h-score using its zone boundaries, aligns all markers to a union time grid, and computes a weighted average composite h. Synthetic zone boundaries `{healthy_min: 0, healthy_max: 2}` are passed to `trajectory_computer` so that `h(composite_h) = composite_h` — output shape is identical to single-marker.

- **data_reader** — `read_timeseries()` reads raw JSON files; `read_multi_marker_timeseries()` reads for multiple markers in one call
- **trajectory_computer** — purely computational, no I/O. Normalizes raw values to a U-shaped health score `h(raw)`, fits a polynomial via `np.polyfit`, evaluates f(x), f'(x), f''(x), assigns zones, maps to one of 27 trajectory states
- **composite_builder** — transforms, time-grid alignment, weighted composite h (new)
- **markerset_reader** — loads markerset instance from DB, merges template + overrides, fetches per-marker zone boundaries (new)
- **report_generator** — dual write: saves full JSON report to `data/reports/{subject}/{report_id}.json` AND inserts metadata row into SQLite

### Markerset System
A **markerset** is a named, saved composition of markers with feature-engineering config. Two levels:
- **Templates** (`markerset_templates` table) — global, reusable marker compositions
- **Instances** (`markerset_instances` table) — per-subject bindings to a template with sparse overrides, or fully custom (no template)

Each marker in a markerset has: `module_id`, `marker_id`, `weight`, `active`, `transform` (type + params), `missing_data` strategy. Zone boundaries are resolved per-marker from the DB at analysis time using the subject's demographics.

### `AnalysisInput` (GraphQL)
```
subject_id, method, timeframe
markerset_id   — use a saved markerset instance (composite mode)
marker_refs    — ad-hoc [{ module_id, marker_id }] list (single-marker uses trajectory_params zone boundaries)
trajectory_params — polynomial_degree, healthy_min, healthy_max, vulnerability_margin
```
Exactly one of `markerset_id` / `marker_refs` must be provided.

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
- **Markerset** — named composition of markers with feature-engineering config; primary input unit for multi-marker analysis

## Frontend (`frontend/`)

Svelte 5 app using runes (`$state`, `$derived`, `$effect`). No external state management or GraphQL client library — raw `fetch` and `WebSocket` via a shared utility.

**GraphQL client:** `frontend/src/lib/gql.js`
- `gql(query, variables)` — queries and mutations
- `gqlUpload(query, variables, fileKey, file)` — file upload mutation (multipart request spec)
- `subscribe(query, variables, onData, onError)` — WebSocket subscription (graphql-transport-ws protocol)

**Components:**
- `request_report_form.svelte` — analysis submission form; method dropdown (from `analysisMethods` query), single-marker vs markerset input mode toggle, `submitAnalysis` + `jobStatus` subscription
- `subject_management.svelte` — subject CRUD + inline dataset/datapoint management
- `add_module_page.svelte` — module, marker, and demographic zone reference CRUD
- `dataset_management.svelte` — **markerset builder**: create/edit templates and per-subject instances with full feature-engineering config (weight, transform, missing data)
- `timegraph_report_page.svelte` — reads report from `localStorage`, renders chart and table
- `timegraph_chart.svelte` / `timegraph_table.svelte` — expect snake_case fields from localStorage

**Important:** The report stored in `localStorage` uses snake_case field names (`health_score`, `f_prime`, `t0_iso`, etc.) to match what `timegraph_chart.svelte` and `timegraph_table.svelte` expect. The GraphQL response (camelCase) is transformed to snake_case in `request_report_form.svelte` before storing.

## GraphQL Schema Files
```
backend/graphql/
  schema.py              # roots: Query, Mutation, Subscription
  context.py             # AppContext — db_path, rawdata_root, methods, redis_pool, etc.
  dataloaders.py         # batch loaders for subjects and markers
  resolvers/
    queries.py           # includes analysisMethods, markersetTemplates, markersetInstances
    mutations.py         # includes markerset CRUD + updated submitAnalysis
    subscriptions.py     # jobStatus WebSocket subscription
  types/
    subject.py           # Subject, ZoneReference
    module.py            # Module, Marker, DemographicZone
    datapoint.py         # Datapoint, Dataset
    analysis.py          # AnalysisJob, TrajectoryReport, AnalysisResult union, AnalysisMethodInfo, MarkerRefInput, AnalysisInput
    markerset.py         # MarkersetTemplate, MarkersetInstance, MarkerFeatureConfig + input types

backend/startup/
  module_loader.py       # loads module_list.json
  analysis_loader.py     # loads analysis_list.json
  module_list.json       # module/marker registry
  analysis_list.json     # analysis method registry

backend/core/
  analysis/
    trajectory_computer.py   # pure computation: normalize → polyfit → 27-state classify
    composite_builder.py     # multi-marker: transforms → h scores → weighted composite
  storage/
    data_reader.py           # read_timeseries + read_multi_marker_timeseries
    markerset_reader.py      # resolve markerset instance → marker list with zone_boundaries
  output/
    report_generator.py      # save JSON + SQLite row

backend/workers/
  analysis_tasks.py      # run_trajectory_analysis (single + composite modes via use_composite flag)
  settings.py            # WorkerSettings
```
