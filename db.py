import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "portfolio.db"

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        # Single-row account table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash REAL NOT NULL
        )
        """)

        # Cash ledger (deposits/withdrawals + any cash-changing events)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cash_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now')),
            event TEXT NOT NULL,              -- 'deposit', 'withdraw', 'buy', 'sell'
            ticker TEXT,
            shares REAL,
            price REAL,
            amount REAL NOT NULL,             -- signed cash delta (+ for deposit/sell, - for withdraw/buy)
            balance_after REAL NOT NULL
        )
        """)

        # Positions table (your portfolio)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            ticker TEXT PRIMARY KEY,
            shares REAL NOT NULL,
            avg_cost REAL NOT NULL
        )
        """)

        # Ensure account row exists
        cur.execute("SELECT cash FROM account WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO account (id, cash) VALUES (1, 0.0)")

        conn.commit()
