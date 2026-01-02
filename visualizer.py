import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dateutil import tz

from db import get_conn, init_db

init_db()

TORONTO_TZ = tz.gettz("America/Toronto")

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
    Profit over time (last 1 hour shown, Toronto time displayed):

      profit(t) = net_worth(t) - net_contrib(t)
      net_contrib(t) = cumulative sum of deposits/withdrawals up to time t

    IMPORTANT:
    - This function is READ-ONLY.
    - It does NOT insert snapshots.
    - Snapshots should be written ONLY by cron (snapshot_job.py) every 5 minutes.
    """

    # Only support 1D for now (ignore other inputs safely)
    tf = str(timeframe).upper().strip()
    if tf != "1D":
        tf = "1D"

    # --- Window: last 1 hour (UTC)
    end_utc = pd.Timestamp.now(tz="UTC")
    start_utc = end_utc - pd.Timedelta(hours=1)

    with get_conn() as conn:
        snaps = pd.read_sql_query(
            """
            SELECT ts, net_worth
            FROM net_worth_history
            ORDER BY ts
            """,
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
        st.info("No snapshots yet — cron hasn’t written any points to net_worth_history.")
        return

    # --- Parse snapshot timestamps as UTC and filter last hour
    snaps["ts"] = _to_utc_aware(snaps["ts"])
    snaps = snaps.dropna(subset=["ts"]).sort_values("ts")
    snaps = snaps[(snaps["ts"] >= start_utc) & (snaps["ts"] <= end_utc)].copy()

    if snaps.empty:
        st.info("No snapshots in the last hour yet. (Cron writes every 5 minutes.)")
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

    # --- Convert to Toronto local time for plotting
    snaps["ts_local"] = snaps["ts"].dt.tz_convert(TORONTO_TZ).dt.tz_localize(None)

    # --- Plot
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((0, 0, 0, 0))

    ax.plot(snaps["ts_local"], snaps["profit"], linewidth=2.0)

    # If only one point, make it visible
    if len(snaps) == 1:
        ax.scatter(snaps["ts_local"], snaps["profit"], s=25)

    ax.set_title("Profit over time (last 1 hour) — Toronto time")
    ax.set_xlabel("Time (Toronto)")
    ax.set_ylabel("Profit ($)")
    ax.grid(True, alpha=0.05)

    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_alpha(0.3)

    # Axis: last 1 hour window in Toronto time
    end_local = pd.Timestamp.now(tz=TORONTO_TZ).tz_localize(None)
    start_local = end_local - pd.Timedelta(hours=1)
    ax.set_xlim(start_local, end_local)

    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    st.pyplot(fig, transparent=True)

    # Optional: show latest point stats
    last = snaps.iloc[-1]
    st.caption(
        f"Latest profit: ${float(last['profit']):.2f} • "
        f"Net worth: ${float(last['net_worth']):.2f} • "
        f"Net contributions: ${float(last['net_contrib']):.2f} • "
        f"Points shown: {len(snaps)} (cron = every 5 min)"
    )