from __future__ import annotations
from db import init_db
from account import load_cash
from portfolio_store import load_portfolio
from data_fetcher import DataFetcher
from net_worth_store import log_net_worth_snapshot

def compute_net_worth_now() -> tuple[float, float, float] | None:
    cash = float(load_cash())
    portfolio_value = 0.0

    missing = []

    for stock in load_portfolio():
        ticker = stock["ticker"]
        shares = float(stock["shares"])

        price = DataFetcher(ticker).get_current_price()
        if price is None:
            missing.append(ticker)
            continue

        portfolio_value += shares * float(price)

    # If ANY ticker failed, skip the snapshot
    if missing:
        print(f"snapshot skipped: missing prices for {', '.join(sorted(set(missing)))}")
        return None

    net_worth = cash + portfolio_value
    return net_worth, cash, portfolio_value


def main() -> None:
    init_db()

    res = compute_net_worth_now()
    if res is None:
        return

    net_worth, cash, pv = res

    log_net_worth_snapshot(
        net_worth=net_worth,
        cash=cash,
        portfolio_value=pv,
        source="cron_5m",
        min_interval_seconds=240,
    )

    print(f"snapshot ok: net_worth={net_worth:.2f} cash={cash:.2f} pv={pv:.2f}")

if __name__ == "__main__":
    main()