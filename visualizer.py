import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from db import get_conn

def plot_profit_history(months: int = 6):
    """
    Profit curve that ignores deposits/withdrawals:
      profit = (cash + market_value) - net_contributions
    Only moves with stock prices (and realized pnl via selling).
    """

    with get_conn() as conn:
        ledger = pd.read_sql_query(
            """
            SELECT ts, event, ticker, shares, price, amount, balance_after
            FROM cash_ledger
            ORDER BY ts
            """,
            conn,
        )

    if ledger.empty:
        st.info("No history yet. Deposit/withdraw/buy/sell to start tracking profit.")
        return

    ledger["ts"] = pd.to_datetime(ledger["ts"])
    ledger["date"] = ledger["ts"].dt.tz_localize(None).dt.normalize()

    end = pd.Timestamp.now().normalize()
    start = end - pd.DateOffset(months=months)

    # Keep ledger entries that could affect holdings/cash in window
    ledger = ledger[ledger["date"] <= end].copy()
    if ledger.empty:
        st.info("No events yet.")
        return

    # Daily index
    days = pd.date_range(start=start, end=end, freq="B")
    if len(days) == 0:
        st.info("Not enough dates in range.")
        return

    # We replay the ledger day-by-day to compute:
    # - cash
    # - shares held per ticker
    # - net contributions (deposit/withdraw only)
    cash = 0.0
    net_contrib = 0.0
    positions = {}  # ticker -> shares

    # Group events by day for fast replay
    by_day = ledger.groupby("date")

    # Collect tickers seen (for price fetch)
    tickers = sorted({t for t in ledger["ticker"].dropna().unique() if str(t).strip()})

    # Fetch prices for all tickers (6 months window)
    price_df = pd.DataFrame(index=days)
    if tickers:
        # yfinance can do multi-ticker download
        px = yf.download(
            tickers=tickers,
            start=(start - pd.DateOffset(days=7)).strftime("%Y-%m-%d"),
            end=(end + pd.DateOffset(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )

        # Normalize into price_df columns (Close series)
        for t in tickers:
            try:
                if isinstance(px.columns, pd.MultiIndex):
                    s = px[(t, "Close")].copy()
                else:
                    # single ticker edge case
                    s = px["Close"].copy()
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                price_df[t] = s.reindex(days).ffill()
            except Exception:
                # if a ticker fails, leave it missing
                pass

        price_df = price_df.ffill()

    # Build curve
    rows = []
    for d in days:
        # Apply all events on this day (in time order)
        if d in by_day.groups:
            day_events = by_day.get_group(d).sort_values("ts")
            for _, e in day_events.iterrows():
                ev = str(e["event"]).lower()
                amt = float(e["amount"]) if pd.notna(e["amount"]) else 0.0
                tkr = str(e["ticker"]).upper().strip() if pd.notna(e["ticker"]) else None
                sh = float(e["shares"]) if pd.notna(e["shares"]) else None

                # Cash always moves by amount (deposit/withdraw/buy/sell)
                cash += amt

                # Contributions track ONLY deposits/withdrawals
                if ev == "deposit":
                    net_contrib += amt  # amt is positive
                elif ev == "withdraw":
                    net_contrib += amt  # amt is negative (so this reduces contributions)

                # Positions update on buys/sells
                if ev == "buy" and tkr and sh:
                    positions[tkr] = positions.get(tkr, 0.0) + sh
                elif ev == "sell" and tkr and sh:
                    positions[tkr] = positions.get(tkr, 0.0) - sh
                    if positions.get(tkr, 0.0) <= 1e-9:
                        positions.pop(tkr, None)

        # Market value at day d
        mv = 0.0
        for tkr, sh in positions.items():
            if tkr in price_df.columns:
                p = price_df.at[d, tkr]
                if pd.notna(p):
                    mv += sh * float(p)

        net_worth = cash + mv
        profit = net_worth - net_contrib

        rows.append({"date": d, "profit": profit, "net_worth": net_worth})

    curve = pd.DataFrame(rows)

    # Always show the line, even if flat
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((0, 0, 0, 0))

    ax.plot(curve["date"], curve["profit"], linewidth=2.0)

    ax.set_title("Profit over time (ignores deposits/withdrawals)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Profit ($)")
    ax.grid(True, alpha=0.05)

    # Dark-mode friendly ticks
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_alpha(0.3)

    st.pyplot(fig, transparent=True)