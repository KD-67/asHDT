# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**asHDT** — a health-data trajectory analysis tool. A FastAPI backend that reads raw biomarker time-series data from the filesystem, fits polynomials to normalized health scores, and classifies each data point into one of 27 discrete trajectory states using zone assignment + two derivatives (f, f', f'').

There is no frontend code in this repo yet; the backend serves a Svelte frontend expected at `http://localhost:5173`.

## Running the Server

```bash
# From the repo root (not from backend/)
uvicorn backend.main:app --reload
```

The server is configured to run from the repo root. All internal imports in `main.py` use mixed styles — some are package-relative (`backend.startup.module_loader`), some are bare (`api.routes`, `core.storage.data_reader`). The working directory **must** be `backend/` for the bare imports to resolve, or PYTHONPATH must include `backend/`.

**Dependencies:** FastAPI, uvicorn, numpy, pydantic (no requirements.txt exists yet).

## Architecture

### Startup Flow (`backend/main.py`)
1. `init_db()` — creates SQLite database and tables (`subjects`, `timegraph_reports`) if they don't exist
2. `load_modules()` — reads `backend/startup/module_list.json` into `app.state.modules`
3. Paths stored in `app.state`: `db_path`, `rawdata_root`, `reports_root`

### Data Pipeline (triggered by `POST /timegraph`)
`routes.py` → `data_reader.read_timeseries()` → `trajectory_computer.compute_trajectory()` → `report_generator.save_timegraph_report()`

- **data_reader** — reads raw JSON files from `data/raw_data/{subject}/{module}/{marker}/`, guided by each marker folder's `index.json`. Returns filtered, sorted datapoints with `parsed_timestamp` datetime objects.
- **trajectory_computer** — purely computational, no I/O. Normalizes raw values to a U-shaped health score `h(raw)`, fits a polynomial via `np.polyfit`, evaluates f(x), f'(x), f''(x), assigns zones (non_pathology / vulnerability / pathology), and maps to one of 27 trajectory states.
- **report_generator** — dual write: saves full JSON report to `data/reports/{subject}/{report_id}.json` AND inserts metadata row into `timegraph_reports` SQLite table.

### Data Layout
```
data/
  raw_data/{subject_id}/{module_id}/{marker_id}/
    index.json          # list of entries with timestamps + filenames
    *.json              # individual datapoint files
  raw_data/{subject_id}/profile.json   # subject demographics
  databases/asHDT.db   # SQLite (gitignored)
  reports/              # generated report JSONs
```

### API Endpoints
- `GET /registry` — returns the module/marker catalog
- `GET /subjects` — lists subject directory names
- `POST /timegraph` — runs full analysis pipeline, returns `report_id`, `datapoints`, and `fit_metadata` (polynomial coefficients for client-side curve rendering)

### Key Domain Concepts
- **Module** — a test or measurement category (e.g. `fitness`, `vtf_stresstest`)
- **Marker** — a specific measurable within a module (e.g. `vo2max`, `100m_sprint`)
- **Health score h(raw)** — U-shaped normalization: `1 - |raw - mid| / half_range`, where h=1 is optimal center, h=0 is boundary of healthy range, h<0 is outside
- **Trajectory state (1–27)** — combination of zone (3) × f' sign (3) × f'' sign (3)
- **Zone boundaries** — `healthy_min`, `healthy_max`, `vulnerability_margin`

## Known Issues

There are several bugs in the current codebase (as of the latest commit):
- `routes.py:49` — `os.dir.join` should be `os.path.join`
- `routes.py:127` — `requested_at` is used before it's defined (line 130)
- `routes.py:152` — missing comma between SQL string and tuple arguments in `conn.execute()`
- `main.py:18` — `MODULES_PATH` resolves incorrectly; points to `../startup/module_list.json` relative to `backend/` but the file lives at `backend/startup/module_list.json`
- Import paths are inconsistent — `main.py` mixes `backend.startup.*` with bare `api.routes`; `routes.py` mixes `core.*` with `backend.startup.*`
- The `subjects` table schema in `init_db()` has a `subject_id` TEXT column but `routes.py` inserts with `INSERT OR IGNORE` keyed on `subject_id` while the PRIMARY KEY is `id` (INTEGER) — the IGNORE will never trigger on duplicate subjects
