import pandas as pd
import yfinance as yf
from db import get_conn, init_db


def safe_last_price(ticker: str):
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def main():
    init_db()

    with get_conn() as conn:
        # cash
        cash = float(
            conn.execute("SELECT cash FROM account WHERE id = 1")
            .fetchone()["cash"]
        )

        # net contributions (deposits + withdrawals)
        net_contrib = float(
            conn.execute("""
                SELECT COALESCE(SUM(amount), 0.0)
                FROM cash_ledger
                WHERE event IN ('deposit', 'withdraw')
            """).fetchone()[0]
        )

        positions = conn.execute(
            "SELECT ticker, shares FROM positions"
        ).fetchall()

    market_value = 0.0
    missing = []

    for r in positions:
        tkr = r["ticker"].upper().strip()
        sh = float(r["shares"])
        if sh <= 0:
            continue

        price = safe_last_price(tkr)
        if price is None:
            missing.append(tkr)
            continue

        market_value += sh * price

    net_worth = cash + market_value
    profit = net_worth - net_contrib

    ts = pd.Timestamp.now(tz="America/Toronto").strftime("%Y-%m-%d %H:%M:%S%z")

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO net_worth_history (ts, net_worth, net_contrib, profit)
            VALUES (?, ?, ?, ?)
        """, (ts, net_worth, net_contrib, profit))
        conn.commit()

    print("Snapshot saved.")
    if missing:
        print("Missing prices for:", ", ".join(missing))


if __name__ == "__main__":
    main()
