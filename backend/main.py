from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import sqlite3, csv, io, re, os, secrets
from datetime import datetime, timedelta
from difflib import SequenceMatcher

app = FastAPI(title="Banking API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware)

DB_PATH = "/data/banking.db"
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
_valid_tokens = set()
security = HTTPBearer(auto_error=False)

# ── DB INIT ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            value_date TEXT,
            amount REAL NOT NULL,
            merchant TEXT NOT NULL,
            category TEXT NOT NULL,
            notes TEXT,
            person1_pct REAL,
            person2_pct REAL,
            is_transfer INTEGER DEFAULT 0,
            is_starting_balance INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            category TEXT NOT NULL,
            use_regex INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO settings VALUES ('person1_name','Partner 1'), ('person2_name','Partner 2');
    """)
    conn.commit()
    conn.close()

init_db()

# ── AUTH ─────────────────────────────────────────────────────────────────────
def check_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not APP_PASSWORD: return True
    if not credentials or credentials.credentials not in _valid_tokens:
        raise HTTPException(401, "Unauthorized")
    return True

@app.post("/api/auth/login")
def login(body: dict):
    if not APP_PASSWORD or body.get("password") == APP_PASSWORD:
        t = secrets.token_hex(32); _valid_tokens.add(t); return {"token": t}
    raise HTTPException(401, "Incorrect password")

# ── NEW: BULK DELETE FIX ─────────────────────────────────────────────────────
class BulkDeleteRequest(BaseModel):
    ids: List[int]

@app.post("/api/transactions/bulk-delete", dependencies=[Depends(check_auth)])
def bulk_delete(req: BulkDeleteRequest):
    conn = get_db()
    try:
        if not req.ids: return {"deleted": 0}
        ph = ",".join("?" * len(req.ids))
        conn.execute(f"DELETE FROM transactions WHERE id IN ({ph})", req.ids)
        conn.commit()
        return {"deleted": len(req.ids)}
    finally:
        conn.close()

# ── IMPROVED: RULE SUGGESTIONS ──────────────────────────────────────────────
@app.get("/api/import/suggest-rules", dependencies=[Depends(check_auth)])
def suggest_rules():
    conn = get_db()
    # Get existing rules to prevent redundant suggestions
    existing_rules = conn.execute("SELECT pattern FROM rules").fetchall()
    patterns = [r['pattern'].lower() for r in existing_rules]
    
    # Logic to find frequent merchants not covered by existing patterns...
    # (Simplified for brevity: check if merchant contains any existing pattern)
    rows = conn.execute("SELECT merchant, category, COUNT(*) as cnt FROM transactions GROUP BY merchant, category HAVING cnt > 2").fetchall()
    suggestions = []
    for r in rows:
        is_redundant = any(p in r['merchant'].lower() for p in patterns)
        if not is_redundant:
            suggestions.append({"merchant": r['merchant'], "category": r['category']})
    conn.close()
    return suggestions[:10]

# (Rest of main.py logic for imports, settings, and stats stays largely the same)
