from db import get_conn, init_db

init_db()

def load_portfolio():
    with get_conn() as conn:
        rows = conn.execute("SELECT ticker, shares, avg_cost FROM positions ORDER BY ticker").fetchall()
        return [
            {"ticker": r["ticker"], "shares": float(r["shares"]), "buy_price": float(r["avg_cost"])}
            for r in rows
        ]

def upsert_position(ticker: str, shares: float, avg_cost: float):
    ticker = ticker.upper().strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO positions (ticker, shares, avg_cost)
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                shares = excluded.shares,
                avg_cost = excluded.avg_cost
            """,
            (ticker, float(shares), float(avg_cost)),
        )
        conn.commit()

def delete_position(ticker: str):
    ticker = ticker.upper().strip()
    with get_conn() as conn:
        conn.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))
        conn.commit()
