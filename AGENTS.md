# AGENTS.md

## Cursor Cloud specific instructions

### Architecture

This is a personal banking/finance tracker with two components:

| Component | Technology | Port | Notes |
|-----------|-----------|------|-------|
| Backend | Python 3 + FastAPI + Uvicorn | 8000 | Single file: `backend/main.py`, SQLite at `/data/banking.db` |
| Frontend | Static HTML (single `frontend/index.html`) + Nginx | 3456 | Nginx proxies `/api/` to backend |

### Running the development environment

**Backend:**
```
mkdir -p /data
APP_PASSWORD="" uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Run from `/workspace/backend`. The `--reload` flag enables hot-reloading on code changes.

**Frontend (Nginx):**
An nginx config is needed to serve the frontend and proxy API calls. See `/etc/nginx/sites-available/banking` if already configured, otherwise create one that:
- Listens on port 3456
- Serves `/workspace/frontend` as root
- Proxies `/api/` to `http://127.0.0.1:8000/api/`

Start nginx with: `nginx` (or `nginx -s reload` if already running).

### Key gotchas

- `DB_PATH` is hardcoded to `/data/banking.db` in `backend/main.py`. You **must** `mkdir -p /data` before starting the backend.
- `init_db()` runs at module import time — if `/data` doesn't exist, the import will fail.
- Auth is disabled when `APP_PASSWORD` env var is empty. Set it to any string to enable token-based auth.
- There are no automated tests in the repository. Use `pytest` with `httpx` for integration tests if needed.
- Lint with: `ruff check backend/main.py` (expect ~163 pre-existing warnings in the current codebase).
- The frontend is a single large HTML file (~125KB) containing all JS/CSS inline.

### Testing API endpoints

Quick smoke test:
```bash
curl -s http://localhost:3456/api/categories
curl -s http://localhost:3456/api/settings
curl -s -X POST http://localhost:3456/api/transactions -H "Content-Type: application/json" -d '{"date":"2026-01-01","amount":-10,"merchant":"Test","category":"Food"}'
```
