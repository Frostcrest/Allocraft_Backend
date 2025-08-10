Deploying Allocraft Backend (FastAPI)

Overview
- App: FastAPI (uvicorn)
- DB: SQLite by default; can use Postgres by setting DATABASE_URL
- CORS: FRONTEND_ORIGINS env var controls allowed origins

Render.com (recommended for dev)
1) Push to GitHub; create a new Web Service in Render pointing to this repo/folder.
2) Render picks up render.yaml. Confirm:
   - Build: pip install -r requirements.txt
   - Start: uvicorn fastapi_project.app.main:app --host 0.0.0.0 --port $PORT
   - Disk: free plan uses /opt/render/data; DATABASE_URL defaults to sqlite:////opt/render/data/allocraft.db
3) Set env vars as needed:
   - FRONTEND_ORIGINS: https://allocraft-lite.onrender.com,https://allocraft-lite-dev.onrender.com
   - SECRET_KEY: generate or paste
   - DATABASE_URL: leave as default for Render disk (or set Postgres URL)
4) Deploy. Visit /healthz for a quick check.

Notes
- Local dev uses .env; copy .env.template -> .env
- DB URL priority: DATABASE_URL env var else sqlite:///./test.db
