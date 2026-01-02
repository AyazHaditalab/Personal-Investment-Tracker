import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dateutil import tz

from db import get_conn, init_db
from account import load_cash
from portfolio_store import load_portfolio
from data_fetcher import DataFetcher
from net_worth_store import log_net_worth_snapshot

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

    net_worth = cash + total_value
    return net_worth, cash, total_value


def _to_utc_aware(series: pd.Series) -> pd.Series:
    """
    Convert a datetime series to tz-aware UTC safely:
    - If naive -> localize to UTC
    - If already tz-aware -> convert to UTC
    """
    s = pd.to_datetime(series, errors="coerce")
    if getattr(s.dt, "tz", None) is None:
        return s.dt.tz_localize("UTC")
    return s.dt.tz_convert("UTC")


def plot_profit_history(timeframe: str = "1D"):
    """
    1D profit over time (Toronto time displayed):

      profit(t) = net_worth(t) - net_contrib(t)
      net_contrib(t) = cumulative sum of deposits/withdrawals up to time t

    Notes:
    - DB timestamps are assumed UTC (SQLite datetime('now')).
    - We only convert to Toronto for plotting.
    - We insert at most one snapshot per minute to avoid spamming points.
    """

    tf = str(timeframe).upper().strip()
    if tf != "1D":
        tf = "1D"

    # --- Insert ONE throttled snapshot
    nw, cash, pv = _compute_net_worth_now()

    has_any_value = (abs(nw) > 1e-9) or (abs(cash) > 1e-9) or (abs(pv) > 1e-9)

    with get_conn() as conn:
        ledger_count = conn.execute("SELECT COUNT(*) AS c FROM cash_ledger").fetchone()["c"]
        has_activity = int(ledger_count) > 0

    if has_any_value or has_activity:
        log_net_worth_snapshot(
            net_worth=nw,
            cash=cash,
            portfolio_value=pv,
            source="visualizer",
            min_interval_seconds=60,
        )

    # --- Load last 24h data
    end_utc = pd.Timestamp.now(tz="UTC")
    start_utc = end_utc - pd.Timedelta(days=1)

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
        st.info("No snapshots yet — nothing to plot.")
        return

    # --- Parse timestamps -> tz-aware UTC and filter window
    snaps["ts"] = _to_utc_aware(snaps["ts"])
    snaps = snaps.dropna(subset=["ts"]).sort_values("ts")
    snaps = snaps[(snaps["ts"] >= start_utc) & (snaps["ts"] <= end_utc)].copy()

    if snaps.empty:
        st.info("No snapshots in the last 24h yet.")
        return

    # --- Compute contributions as-of each snapshot
    if contrib.empty:
        snaps["net_contrib"] = 0.0
    else:
        contrib["ts"] = _to_utc_aware(contrib["ts"])
        contrib = contrib.dropna(subset=["ts"]).sort_values("ts")
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

    # --- Convert to Toronto time for plotting
    snaps["ts_local"] = snaps["ts"].dt.tz_convert(TORONTO_TZ).dt.tz_localize(None)

    # --- Plot
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((0, 0, 0, 0))

    ax.plot(snaps["ts_local"], snaps["profit"], linewidth=2.0)

    if len(snaps) == 1:
        ax.scatter(snaps["ts_local"], snaps["profit"], s=25)

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

    # ✅ FIX: force a 24h local window + hourly ticks (prevents the 00:00 spam)
    end_local = pd.Timestamp.now(tz=TORONTO_TZ).tz_localize(None)
    start_local = end_local - pd.Timedelta(hours=24)
    ax.set_xlim(start_local, end_local)

    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    st.pyplot(fig, transparent=True)