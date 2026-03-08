from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import csv
import io
import re
from datetime import datetime
from typing import List, Optional

DB = "bank.db"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PERSON1 = "Anthony"
PERSON2 = "Sam"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = db()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            value_date TEXT,
            amount REAL,
            merchant TEXT,
            category TEXT,
            person1_pct REAL,
            person2_pct REAL
        );

        CREATE TABLE IF NOT EXISTS rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT,
            category TEXT
        );
        """
    )

    conn.commit()


init()


def normalize_merchant(name: str):
    name = name.upper()
    name = re.sub(r"\d+", "", name)
    name = name.split(" AU")[0]
    name = name.split(" AUS")[0]
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def apply_rules(merchant, conn):

    rows = conn.execute(
        "SELECT pattern, category FROM rules ORDER BY length(pattern) DESC"
    ).fetchall()

    for r in rows:
        if r["pattern"] in merchant:
            return r["category"]

    return "Other"


def parse_value_date(text):

    m = re.search(r"Value Date: (\d{2}/\d{2}/\d{4})", text)
    if m:
        return m.group(1)

    return None


def detect_duplicate(tx, conn):

    rows = conn.execute(
        "SELECT * FROM transactions WHERE amount=?",
        (tx["amount"],),
    ).fetchall()

    for r in rows:

        if r["merchant"] == tx["merchant"]:
            return True

    return False


class ImportRequest(BaseModel):
    expected_balance: Optional[float] = None


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...), expected_balance: Optional[float] = None):

    content = await file.read()
    text = content.decode()

    reader = csv.reader(io.StringIO(text))

    conn = db()

    rows = []
    duplicates = []

    for row in reader:

        date = row[0]
        amount = float(row[1].replace('"', ""))
        merchant = row[2].replace('"', "")
        balance = float(row[3].replace('"', ""))

        value_date = parse_value_date(merchant)

        merchant = normalize_merchant(merchant)

        tx = {
            "date": date,
            "value_date": value_date,
            "amount": amount,
            "merchant": merchant,
            "balance": balance,
        }

        if detect_duplicate(tx, conn):
            duplicates.append(tx)
        else:
            rows.append(tx)

    import_sum = sum(r["amount"] for r in rows)

    base_balance = 0

    r = conn.execute("SELECT SUM(amount) as s FROM transactions").fetchone()
    if r["s"]:
        base_balance = r["s"]

    best_set = []
    best_diff = 1e18

    if expected_balance is not None:

        dup_amounts = [d["amount"] for d in duplicates]

        from itertools import combinations

        for i in range(len(dup_amounts) + 1):
            for combo in combinations(range(len(dup_amounts)), i):

                s = sum(dup_amounts[j] for j in combo)

                final = base_balance + import_sum + s

                diff = abs(final - expected_balance)

                if diff < best_diff:
                    best_diff = diff
                    best_set = combo

    import_dups = [duplicates[i] for i in best_set]

    all_import = rows + import_dups

    for tx in all_import:

        category = apply_rules(tx["merchant"], conn)

        conn.execute(
            """
            INSERT INTO transactions(date,value_date,amount,merchant,category,person1_pct,person2_pct)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                tx["date"],
                tx["value_date"],
                tx["amount"],
                tx["merchant"],
                category,
                0.5,
                0.5,
            ),
        )

    conn.commit()

    return {
        "imported": len(all_import),
        "duplicates_skipped": len(duplicates) - len(import_dups),
        "suggested_import": len(all_import),
        "confidence": "high",
    }


@app.get("/api/transactions")
def transactions():

    conn = db()

    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY date DESC"
    ).fetchall()

    return [dict(r) for r in rows]


@app.post("/api/transactions/bulk-delete")
def bulk_delete(ids: List[int]):

    conn = db()

    conn.executemany(
        "DELETE FROM transactions WHERE id=?",
        [(i,) for i in ids],
    )

    conn.commit()

    return {"deleted": len(ids)}


@app.get("/api/monthly")
def monthly():

    conn = db()

    rows = conn.execute(
        """
        SELECT substr(date,4,7) as month,
        SUM(amount*person1_pct) as p1,
        SUM(amount*person2_pct) as p2
        FROM transactions
        GROUP BY month
        ORDER BY month
        """
    ).fetchall()

    return [dict(r) for r in rows]


@app.get("/api/spending-alerts")
def alerts():

    conn = db()

    rows = conn.execute(
        """
        SELECT category,SUM(amount) as total
        FROM transactions
        WHERE amount < 0
        GROUP BY category
        """
    ).fetchall()

    alerts = []

    for r in rows:
        if abs(r["total"]) > 800:
            alerts.append(
                f"{r['category']} spending high: ${abs(r['total']):.2f}"
            )

    return alerts
