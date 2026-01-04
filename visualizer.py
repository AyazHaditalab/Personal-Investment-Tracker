import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dateutil import tz

from db import get_conn, init_db

init_db()

TORONTO_TZ = tz.gettz("America/Toronto")

RANGE_OPTIONS = {
    "1H": pd.Timedelta(hours=1),
    "12H": pd.Timedelta(hours=12),
    "24H": pd.Timedelta(hours=24),
    "1W": pd.Timedelta(days=7),
    "1M": pd.Timedelta(days=30),
}


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


@st.cache_data(ttl=10, show_spinner=False)
def _load_profit_series():
    """
    Read snapshots + contribution ledger from SQLite.

    Cached briefly to avoid hammering SQLite on every Streamlit rerun.
    TTL is short so cron updates still show up quickly.
    """
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
    return snaps, contrib


def plot_profit_history(timeframe: str = "1H"):
    """
    Profit over time (Toronto time displayed):

      profit(t) = net_worth(t) - net_contrib(t)
      net_contrib(t) = cumulative sum of deposits/withdrawals up to time t

    IMPORTANT:
    - This function is READ-ONLY.
    - It does NOT insert snapshots.
    - Snapshots should be written ONLY by cron (snapshot_job.py) every 5 minutes.
    """

    # -------------------------
    # UI: Range selector (sticky)
    # -------------------------
    default_tf = str(timeframe).upper().strip()
    if default_tf not in RANGE_OPTIONS:
        default_tf = "1H"

    options = list(RANGE_OPTIONS.keys())
    default_index = options.index(default_tf)

    cols = st.columns([1, 6])
    with cols[0]:
        tf = st.selectbox(
            "Range",
            options,
            index=default_index,
            key="profit_range",
            label_visibility="collapsed",
        )
    window = RANGE_OPTIONS[tf]

    # Compute time window (UTC)
    end_utc = pd.Timestamp.now(tz="UTC")
    start_utc = end_utc - window

    # Load data (cached)
    snaps, contrib = _load_profit_series()

    if snaps.empty:
        st.info("No snapshots yet — cron hasn’t written any points to net_worth_history.")
        return

    # Parse snapshots -> UTC and filter window
    snaps["ts"] = _to_utc_aware(snaps["ts"])
    snaps = snaps.dropna(subset=["ts"]).sort_values("ts")
    snaps = snaps[(snaps["ts"] >= start_utc) & (snaps["ts"] <= end_utc)].copy()

    if snaps.empty:
        label = tf.replace("H", " hour").replace("W", " week").replace("M", " month")
        st.info(f"No snapshots in the selected range ({label}). (Cron writes every 5 minutes.)")
        return

    # Compute net contributions as-of each snapshot
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

    # Convert to Toronto local time for plotting
    snaps["ts_local"] = snaps["ts"].dt.tz_convert(TORONTO_TZ).dt.tz_localize(None)

    # -------------------------
    # Plot
    # -------------------------
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((0, 0, 0, 0))

    ax.plot(snaps["ts_local"], snaps["profit"], linewidth=2.0)

    if len(snaps) == 1:
        ax.scatter(snaps["ts_local"], snaps["profit"], s=25)

    title_tf = tf
    ax.set_title(f"Profit over time ({title_tf}) — Toronto time")
    ax.set_xlabel("Time (Toronto)")
    ax.set_ylabel("Profit ($)")
    ax.grid(True, alpha=0.05)

    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_alpha(0.3)

    # Axis window in Toronto time (match selected range)
    end_local = end_utc.tz_convert(TORONTO_TZ).tz_localize(None)
    start_local = start_utc.tz_convert(TORONTO_TZ).tz_localize(None)
    ax.set_xlim(start_local, end_local)

    # Tick formatting based on range
    if window <= pd.Timedelta(hours=1):
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    elif window <= pd.Timedelta(hours=12):
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    elif window <= pd.Timedelta(days=1):
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    elif window <= pd.Timedelta(days=7):
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    st.pyplot(fig, transparent=True)

    last = snaps.iloc[-1]
    st.caption(
    "Profit history is generated from net worth snapshots. "
    "With a background scheduler (e.g. cron), snapshots update automatically; "
    "otherwise they update on page refresh."
    )
