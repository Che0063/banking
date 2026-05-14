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
- The frontend is a single-file React app (React 18.2.0 + Babel standalone via CDN). No build step, no npm — Babel transpiles JSX in-browser at runtime.
- **DELETE with body**: Nginx strips request bodies from DELETE requests. Bulk-delete uses `POST /api/transactions/bulk-delete` as a workaround.
- **Bulk edit** uses `PUT /api/transactions/bulk-edit`.

### Data conventions

- **Amounts**: negative = expense, positive = income.
- **Splits**: stored as 0.0–1.0 fractions (0.5 = 50%). `person1_pct + person2_pct` should equal 1.0. NULL means split not yet assigned.
- **Dates**: Two date fields — `date` (statement/desktop date) and `value_date` (mobile/settlement date). Transactions without `value_date` are "Pending". Sorting/filtering uses `COALESCE(value_date, date)`.
- **Categories**: `Unassigned` means no category assigned yet. `is_transfer=1` transactions are excluded from income/expense summaries.

### Import workflow (two-step)

1. POST to `/api/import/commbank/parse` or `/api/import/xlsx/parse` — returns parsed rows + duplicate flags (no DB write)
2. POST to `/api/import/confirm` with per-row actions (`import`, `skip`, `replace`) — writes to DB

### Testing API endpoints

Quick smoke test:
```bash
curl -s http://localhost:3456/api/categories
curl -s http://localhost:3456/api/settings
curl -s "http://localhost:3456/api/transactions?page=1&per_page=10"
curl -s -X POST http://localhost:3456/api/transactions -H "Content-Type: application/json" -d '{"date":"2026-01-01","amount":-10,"merchant":"Test","category":"Food"}'
```
