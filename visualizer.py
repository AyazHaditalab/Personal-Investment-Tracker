import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dateutil import tz

from db import get_conn, init_db
from account import load_cash
from portfolio_store import load_portfolio
from data_fetcher import DataFetcher

init_db()

TORONTO_TZ = tz.gettz("America/Toronto")


def _compute_net_worth_now():
    cash = float(load_cash())
    total_value = 0.0
    for stock in load_portfolio():
        ticker = stock["ticker"]
        shares = float(stock["shares"])
        price = DataFetcher(ticker).get_current_price()
        if price is None:
            continue
        total_value += shares * float(price)
    return cash + total_value, cash, total_value


def _insert_snapshot():
    # store ts explicitly as Toronto local wall time
    now_local = pd.Timestamp.now(tz=TORONTO_TZ).tz_localize(None)
    ts_str = now_local.strftime("%Y-%m-%d %H:%M:%S")

    nw, cash, pv = _compute_net_worth_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO net_worth_history (ts, net_worth, cash, portfolio_value, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts_str, float(nw), float(cash), float(pv), "visualizer_autosnap"),
        )
        conn.commit()


def plot_profit_history():
    """
    1D Profit over time (Toronto time shown):
      Profit(t) = NetWorth(t) - NetContrib(t)

    - Ensures at least 1 snapshot exists by inserting one on render.
    - Converts timestamps to Toronto local time and plots as naive datetimes (matplotlib-safe).
    """

    # Always create a point on render
    _insert_snapshot()

    end_local = pd.Timestamp.now(tz=TORONTO_TZ).tz_localize(None)
    start_local = end_local - pd.Timedelta(days=1)

    with get_conn() as conn:
        snaps = pd.read_sql_query(
            "SELECT ts, net_worth FROM net_worth_history ORDER BY ts",
            conn,
        )
        contrib = pd.read_sql_query(
            """
            SELECT ts, amount
            FROM cash_ledger
            WHERE event IN ('deposit', 'withdraw')
            ORDER BY ts
            """,
            conn,
        )

    if snaps.empty:
        st.error("No snapshots found in net_worth_history.")
        return

    # Snapshots are stored as Toronto-local naive timestamps
    snaps["ts"] = pd.to_datetime(snaps["ts"], errors="coerce")
    snaps = snaps.dropna(subset=["ts"]).sort_values("ts")
    snaps = snaps[(snaps["ts"] >= start_local) & (snaps["ts"] <= end_local)].copy()

    if snaps.empty:
        st.info("No snapshots in the last 24h yet.")
        return

    # Contributions: SQLite default datetime('now') is typically UTC naive.
    # Interpret as UTC -> convert to Toronto -> drop tz to make naive Toronto time.
    if contrib.empty:
        snaps["net_contrib"] = 0.0
    else:
        contrib["ts"] = pd.to_datetime(contrib["ts"], errors="coerce")
        contrib = contrib.dropna(subset=["ts"]).sort_values("ts")

        contrib["ts"] = contrib["ts"].dt.tz_localize("UTC").dt.tz_convert(TORONTO_TZ).dt.tz_localize(None)
        contrib["cum_contrib"] = contrib["amount"].astype(float).cumsum()

        snaps = pd.merge_asof(
            snaps.sort_values("ts"),
            contrib[["ts", "cum_contrib"]].sort_values("ts"),
            on="ts",
            direction="backward",
            allow_exact_matches=True,
        )
        snaps["net_contrib"] = snaps["cum_contrib"].fillna(0.0)
        snaps.drop(columns=["cum_contrib"], inplace=True)

    snaps["profit"] = snaps["net_worth"].astype(float) - snaps["net_contrib"].astype(float)

    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((0, 0, 0, 0))

    ax.plot(snaps["ts"], snaps["profit"], linewidth=2.0)

    ax.set_title("Profit over time (1D) — Toronto time")
    ax.set_xlabel("Time (Toronto)")
    ax.set_ylabel("Profit ($)")
    ax.grid(True, alpha=0.05)

    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_alpha(0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    st.pyplot(fig, transparent=True)

    last = snaps.iloc[-1]
    st.caption(
        f"Latest profit: ${float(last['profit']):.2f} • "
        f"Net worth: ${float(last['net_worth']):.2f} • "
        f"Net contributions: ${float(last['net_contrib']):.2f}"
    )
