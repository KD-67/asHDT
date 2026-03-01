# This is the file that must be run to start the server. It establishes all the paths to relevant files, makes sure the backend knows what
# port the frontend is running on, connects to the SQLite database, and store some important paths a app.state so they don't have to keep 
# being imported every time they're needed.

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.startup.module_loader import load_modules
from backend.startup.database_logistics import init_db
from backend.api.routes import router

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))                           # resolves to: "c:\Users\kevin\proj\asHDT\backend"
REPO_ROOT    = os.path.dirname(BASE_DIR)                                            # resolves to: "c:\Users\kevin\proj\asHDT"
DATA_DIR     = os.path.join(REPO_ROOT, "data")                                      # resolves to: "c:\Users\kevin\proj\asHDT\data"
DB_PATH      = os.path.join(DATA_DIR, "databases", "asHDT.db")                      # resolves to: "c:\Users\kevin\proj\asHDT\data\databases\asHDT.db"
RAWDATA_ROOT = os.path.join(DATA_DIR, "raw_data")                                   # resolves to: "c:\Users\kevin\proj\asHDT\data\raw_data"
REPORTS_ROOT = os.path.join(DATA_DIR, "reports")                                    # resolves to: "c:\Users\kevin\proj\asHDT\data\reports"
MODULES_PATH = os.path.join(BASE_DIR, "startup", "module_list.json")                # resolves to: "c:\Users\kevin\proj\asHDT\backend\startup\module_list.json"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
def startup():
    init_db(DB_PATH)
    app.state.modules     = load_modules(MODULES_PATH)
    app.state.db_path      = DB_PATH
    app.state.rawdata_root = RAWDATA_ROOT
    app.state.reports_root = REPORTS_ROOT