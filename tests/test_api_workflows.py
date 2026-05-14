import os
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


def load_app(db_path):
    source = Path("backend/main.py").read_text().replace(
        'DB_PATH = "/data/banking.db"', f"DB_PATH = {db_path!r}"
    )
    module = types.ModuleType("tested_main")
    exec(compile(source, "backend/main.py", "exec"), module.__dict__)
    module.APP_PASSWORD = "pw"
    module._valid_tokens.clear()
    return module


class ApiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = load_app(os.path.join(self.tmp.name, "banking.db"))
        self.client = TestClient(self.main.app)
        login = self.client.post("/api/auth/login", json={"password": "pw"})
        self.assertEqual(login.status_code, 200, login.text)
        self.headers = {"Authorization": f"Bearer {login.json()['token']}"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_history_audit_exports_and_restore(self):
        self.assertEqual(self.client.get("/api/backup?token=bad").status_code, 401)
        self.assertEqual(self.client.get("/api/backup", headers=self.headers).status_code, 200)

        transfer = self.client.post("/api/transactions", headers=self.headers, json={
            "date": "2026-01-01", "value_date": "2026-01-02", "amount": -100,
            "merchant": "Transfer demo", "category": "Transfer", "notes": None,
            "person1_pct": 0.25, "is_transfer": True, "is_starting_balance": False,
        })
        self.assertEqual(transfer.status_code, 200, transfer.text)
        self.assertEqual(transfer.json()["person1_amount"], -25)

        csv_export = self.client.get("/api/export/csv?categories=Transfer", headers=self.headers)
        self.assertEqual(csv_export.status_code, 200, csv_export.text)
        self.assertIn("Transfer demo", csv_export.text)

        confirm = self.client.post("/api/import/confirm", headers=self.headers, json={"rows": [
            {"date": "2026-02-01", "value_date": "2026-02-05", "amount": -5, "merchant": "Later",
             "category": "Food", "notes": None, "person1_pct": 0.5, "person2_pct": 0.5,
             "is_transfer": 0, "action": "import", "_source": "test"},
            {"date": "2026-02-02", "value_date": "2026-02-03", "amount": -6, "merchant": "Earlier",
             "category": "Food", "notes": None, "person1_pct": 0.5, "person2_pct": 0.5,
             "is_transfer": 0, "action": "import", "_source": "test"},
        ]})
        self.assertEqual(confirm.status_code, 200, confirm.text)
        session = self.client.get("/api/import/sessions", headers=self.headers).json()[0]
        rows = self.client.get(f"/api/import/sessions/{session['id']}/transactions", headers=self.headers).json()
        self.assertEqual([r["merchant"] for r in rows], ["Earlier", "Later"])

        remove = self.client.delete(
            f"/api/import/sessions/{session['id']}/transactions/{rows[0]['id']}",
            headers=self.headers,
        )
        self.assertEqual(remove.status_code, 200, remove.text)
        self.assertEqual(remove.json()["remaining"], 1)

        preset = self.client.post("/api/import/presets", headers=self.headers, json={
            "name": "CommBank monthly", "source": "commbank", "notes": "Monthly CSV",
        })
        self.assertEqual(preset.status_code, 200, preset.text)
        self.assertEqual(self.client.get("/api/import/presets", headers=self.headers).json()[0]["source"], "commbank")

        old_db = os.path.join(self.tmp.name, "old.db")
        conn = sqlite3.connect(old_db)
        conn.executescript("""
        CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT,date TEXT NOT NULL,amount REAL NOT NULL,merchant TEXT NOT NULL,category TEXT NOT NULL,notes TEXT,person1_pct REAL,person2_pct REAL,is_transfer INTEGER DEFAULT 0,created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,is_default INTEGER DEFAULT 0);
        CREATE TABLE rules (id INTEGER PRIMARY KEY AUTOINCREMENT,pattern TEXT NOT NULL,category TEXT NOT NULL,use_regex INTEGER DEFAULT 0,created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE import_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,imported_at TEXT DEFAULT (datetime('now')),source TEXT,count INTEGER);
        CREATE TABLE import_session_ids (session_id INTEGER,transaction_id INTEGER);
        """)
        conn.commit(); conn.close()
        with open(old_db, "rb") as backup:
            restore = self.client.post(
                "/api/restore", headers=self.headers,
                files={"file": ("old.db", backup, "application/octet-stream")},
            )
        self.assertEqual(restore.status_code, 200, restore.text)
        conn = sqlite3.connect(self.main.DB_PATH)
        tx_cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()}
        audit_rows = conn.execute("SELECT action FROM audit_logs").fetchall()
        conn.close()
        self.assertIn("value_date", tx_cols)
        self.assertTrue(any(row[0] == "restore" for row in audit_rows))


if __name__ == "__main__":
    unittest.main()
