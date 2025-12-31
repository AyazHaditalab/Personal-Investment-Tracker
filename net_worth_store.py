from __future__ import annotations
from db import get_conn, init_db

init_db()

def log_net_worth_snapshot(
    *,
    net_worth: float,
    cash: float,
    portfolio_value: float,
    source: str = "unknown",
    min_interval_seconds: int = 300,
) -> bool:
    """
    Insert a snapshot into net_worth_history, but throttle inserts:
    - If the most recent snapshot is newer than min_interval_seconds, do nothing.

    Returns True if inserted, False if skipped.
    """
    net_worth = float(net_worth)
    cash = float(cash)
    portfolio_value = float(portfolio_value)
    min_interval_seconds = int(min_interval_seconds)

    with get_conn() as conn:
        # SQLite datetime('now') is UTC; compare using julianday differences.
        row = conn.execute(
            """
            SELECT ts
            FROM net_worth_history
            ORDER BY ts DESC
            LIMIT 1
            """
        ).fetchone()

        if row is not None:
            last_ts = row["ts"]
            diff_seconds = conn.execute(
                """
                SELECT (julianday('now') - julianday(?)) * 86400.0 AS diff_seconds
                """,
                (last_ts,),
            ).fetchone()["diff_seconds"]

            if diff_seconds is not None and float(diff_seconds) < min_interval_seconds:
                return False

        conn.execute(
            """
            INSERT INTO net_worth_history (net_worth, cash, portfolio_value, source)
            VALUES (?, ?, ?, ?)
            """,
            (net_worth, cash, portfolio_value, source),
        )
        conn.commit()
        return True
