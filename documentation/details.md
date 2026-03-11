**Run the backend from cli:**
# Terminal 1 — Redis (make sure docker is running)
docker run -d -p 6379:6379 redis:alpine

# Terminal 2 — ARQ worker (from repo root)
arq backend.workers.settings.WorkerSettings

# Terminal 3 — FastAPI server (from repo root)
uvicorn backend.main:app --reload

##### Run the frontend from cli:
cd frontend
npm run dev
http://localhost:5173

##### Run the Stucturizr C4 diagrams:
Make sure docker desktop is running
docker compose -f documentation/architecture/docker-compose.yml up   
Open at http://localhost:8080


