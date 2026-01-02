import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "portfolio.db"

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _add_column_if_missing(cur: sqlite3.Cursor, table: str, col: str, col_def: str):
    """
    SQLite doesn't support IF NOT EXISTS for ADD COLUMN in older versions,
    so we check via PRAGMA table_info and add the column if it's missing.
    """
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}  # row[1] = column name
    if col not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        # -----------------------------
        # Single-row account table
        # -----------------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash REAL NOT NULL
        )
        """)

        # -----------------------------
        # Cash ledger
        # -----------------------------
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

        # -----------------------------
        # Positions table
        # -----------------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            ticker TEXT PRIMARY KEY,
            shares REAL NOT NULL,
            avg_cost REAL NOT NULL
        )
        """)

        # -----------------------------
        # Net worth snapshots (for profit-over-time)
        # Keep existing columns + add new optional fields.
        # -----------------------------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS net_worth_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now')),

            net_worth REAL NOT NULL,
            cash REAL NOT NULL,
            portfolio_value REAL NOT NULL,

            source TEXT,

            -- NEW (optional): profit tracking fields
            net_contrib REAL,
            profit REAL
        )
        """)

        # If this table already existed from older versions, ensure new columns exist
        _add_column_if_missing(cur, "net_worth_history", "net_contrib", "REAL")
        _add_column_if_missing(cur, "net_worth_history", "profit", "REAL")

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_net_worth_history_ts
        ON net_worth_history(ts)
        """)

        # -----------------------------
        # Ensure account row exists
        # -----------------------------
        cur.execute("SELECT cash FROM account WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO account (id, cash) VALUES (1, 0.0)")

        conn.commit()
