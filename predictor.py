import yfinance as yf
import numpy as np
import pandas as pd

from dataclasses import dataclass
from sklearn.linear_model import LinearRegression, Ridge

DEFAULT_HORIZON_THRESHOLDS = {
    1: 0.003,   # 0.3%
    3: 0.006,   # 0.6%
    5: 0.010,   # 1.0%
    10: 0.020,  # 2.0%
    20: 0.040,  # 4.0%
}

@dataclass
class EvalResults:
    metrics: dict
    test_df: pd.DataFrame  # includes date, actual_return, pred_return, actual_price, pred_price


class Predictor:
    """
    Predictor v2: predicts next-day returns (not raw price trend), uses time-based split, and reports metrics.

    Key methods:
      - fit(model="ridge")
      - evaluate() -> dict metrics
      - predict_next(n_days=5) -> DataFrame with dates + predicted return + predicted price
      - signal(...) -> dict with BUY/HOLD/SELL and confidence note
      - get_test_plot_data() -> DataFrame for plotting predicted vs actual on test period
    """

    def __init__(self, ticker: str, period: str = "2y", interval: str = "1d"):
        self.ticker = ticker.upper().strip()
        self.period = period
        self.interval = interval

        self.raw = self._get_historical_data()
        self.price_col = self._choose_price_column(self.raw)

        self.feature_cols: list[str] = []
        self.model_name: str | None = None
        self.model = None

        self._prepared = None  # prepared df with features + target
        self._split = None     # dict with train/test matrices
        self._eval: EvalResults | None = None

    # ---------- Data ----------

    def _get_historical_data(self) -> pd.DataFrame:
        stock = yf.Ticker(self.ticker)
        df = stock.history(period=self.period, interval=self.interval)
        if df is None or df.empty:
            raise ValueError(f"No historical data returned for ticker '{self.ticker}'.")
        df = df.reset_index()
        # Standardize date column name
        if "Date" not in df.columns:
            # yfinance sometimes returns Datetime
            for c in df.columns:
                if str(c).lower() in {"datetime", "date"}:
                    df.rename(columns={c: "Date"}, inplace=True)
                    break
        df = df.sort_values("Date").reset_index(drop=True)
        return df

    @staticmethod
    def _choose_price_column(df: pd.DataFrame) -> str:
        # Prefer Adj Close (more realistic for splits/dividends), fallback to Close.
        if "Adj Close" in df.columns and df["Adj Close"].notna().any():
            return "Adj Close"
        if "Close" in df.columns and df["Close"].notna().any():
            return "Close"
        raise ValueError("Neither 'Adj Close' nor 'Close' found in historical data.")

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)

        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    # ---------- Features / Split ----------

    def prepare_features(
        self,
        horizon: int = 1,
        lags: tuple[int, ...] = (1, 2, 5, 10),
        ma_windows: tuple[int, ...] = (5, 10, 20),
        vol_windows: tuple[int, ...] = (5, 10, 20),
        include_volume: bool = True,
        rsi_period: int = 14,
        rsi_low: float = 30.0,
        rsi_high: float = 70.0,
    ) -> pd.DataFrame:
        df = self.raw[["Date", self.price_col] + (["Volume"] if "Volume" in self.raw.columns else [])].copy()
        df.rename(columns={self.price_col: "Price"}, inplace=True)

        # Returns (pct return; simple + interpretable)
        df["ret_1"] = df["Price"].pct_change()

        # ----- RSI (nonlinear-friendly features) -----
        df["rsi_14"] = self._rsi(df["Price"], period=rsi_period)

        # Instead of a centered RSI (which ridge often shrinks / cancels with MA features),
        # use "extremes" that behave linearly when the market is oversold/overbought.
        df["rsi_oversold"] = np.maximum(0.0, (rsi_low - df["rsi_14"]) / rsi_low)              # 0..1+
        df["rsi_overbought"] = np.maximum(0.0, (df["rsi_14"] - rsi_high) / (100.0 - rsi_high))  # 0..1+

        # (Optional) keep a mild centered RSI if you want, but default OFF:
        # df["rsi_centered"] = (df["rsi_14"] - 50.0) / 50.0

        # Lagged returns
        for k in lags:
            df[f"ret_lag_{k}"] = df["ret_1"].shift(k)

        # MA distance features: (price / MA - 1)
        for w in ma_windows:
            ma = df["Price"].rolling(w).mean()
            df[f"ma_dist_{w}"] = (df["Price"] / ma) - 1.0

        # Volatility of returns
        for w in vol_windows:
            df[f"vol_{w}"] = df["ret_1"].rolling(w).std()

        # Volume features (optional)
        if include_volume and "Volume" in df.columns:
            df["vol_chg_1"] = df["Volume"].pct_change()
            df["vol_roll_10"] = df["Volume"].rolling(10).mean()
            df["vol_dist_10"] = (df["Volume"] / df["vol_roll_10"]) - 1.0

        # Target: H-day forward return
        df["y"] = (df["Price"].shift(-horizon) / df["Price"]) - 1.0

        # Drop rows with NaNs introduced by rolling/shift
        df = df.dropna().reset_index(drop=True)

        # Feature columns (everything except date/price/ret_1/y and raw volume roll column)
        exclude = {"Date", "Price", "ret_1", "y", "Volume", "vol_roll_10"}
        self.feature_cols = [c for c in df.columns if c not in exclude]

        self._prepared = df
        self._eval = None
        return df


    def train_test_split(self, test_size: int = 60) -> dict:
        if self._prepared is None:
            self.prepare_features()

        df = self._prepared
        if len(df) <= test_size + 30:
            # Ensure enough training data
            test_size = max(20, min(test_size, len(df) // 3))

        split_idx = len(df) - test_size
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()

        X_train = train_df[self.feature_cols].to_numpy()
        y_train = train_df["y"].to_numpy()

        X_test = test_df[self.feature_cols].to_numpy()
        y_test = test_df["y"].to_numpy()

        self._split = {
            "train_df": train_df,
            "test_df": test_df,
            "X_train": X_train,
            "y_train": y_train,
            "X_test": X_test,
            "y_test": y_test,
        }
        self._eval = None
        return self._split

    # ---------- Model ----------

    def fit(self, model="ridge", horizon=5, test_size=60, ridge_alpha=1.0):
        model = model.lower().strip()
        if model not in {"baseline", "linear", "ridge"}:
            raise ValueError("model must be one of: baseline, linear, ridge")

        self.model_name = model
        self.prepare_features(horizon=horizon)
        self.train_test_split(test_size=test_size)
        self.horizon = horizon

        X_train = self._split["X_train"]
        y_train = self._split["y_train"]

        if model == "baseline":
            # No fitting; baseline predicts 0 return (i.e., tomorrow same price)
            self.model = None
        elif model == "linear":
            self.model = LinearRegression()
            self.model.fit(X_train, y_train)
        else:
            self.model = Ridge(alpha=ridge_alpha)
            self.model.fit(X_train, y_train)

        self._eval = None
        return self

    # ---------- Evaluation ----------

    def evaluate(self) -> dict:
        if self._split is None:
            self.fit(model="ridge")

        test_df = self._split["test_df"].copy()
        X_test = self._split["X_test"]
        y_test = self._split["y_test"]

        if self.model_name == "baseline":
            y_pred = np.zeros_like(y_test)
        else:
            y_pred = self.model.predict(X_test)

        # Metrics on returns
        mae = float(np.mean(np.abs(y_pred - y_test)))
        rmse = float(np.sqrt(np.mean((y_pred - y_test) ** 2)))
        directional_acc = float(np.mean((np.sign(y_pred) == np.sign(y_test)).astype(float)))

        # Convert to implied price path for plotting on test window (one-step ahead)
        # We align prediction with "next-day return", so the implied next price is:
        # next_price = current_price * (1 + pred_return)
        # Use current Price column in prepared df
        test_df["pred_return"] = y_pred
        test_df["actual_return"] = y_test
        test_df["pred_next_price"] = test_df["Price"] * (1.0 + test_df["pred_return"])
        test_df["actual_next_price"] = test_df["Price"] * (1.0 + test_df["actual_return"])

        metrics = {
            "mae_return": mae,
            "rmse_return": rmse,
            "directional_accuracy": directional_acc,
            "test_points": int(len(test_df)),
            "model": self.model_name,
            "price_column_used": self.price_col,
        }

        self._eval = EvalResults(metrics=metrics, test_df=test_df)
        return metrics

    def get_test_plot_data(self) -> pd.DataFrame:
        if self._eval is None:
            self.evaluate()
        # Return a tidy dataframe for plotting
        df = self._eval.test_df[["Date", "Price", "pred_next_price", "actual_next_price", "pred_return", "actual_return"]].copy()
        return df.reset_index(drop=True)

    # ---------- Forecast ----------

    def predict_horizon(self):
        if self.model_name is None:
            raise RuntimeError("Model not fit.")

        latest = self._prepared.iloc[-1]
        X = latest[self.feature_cols].to_numpy().reshape(1, -1)

        if self.model_name == "baseline":
            pred_return = 0.0
        else:
            pred_return = float(self.model.predict(X)[0])

        current_price = float(self.raw[self.price_col].iloc[-1])
        pred_price = current_price * (1.0 + pred_return)

        return {
            "horizon_days": self.horizon,
            "pred_return": pred_return,
            "current_price": current_price,
            "pred_price": pred_price,
        }

    def _build_feature_row_from_history(self, prices: list[float], volumes: list[float] | None) -> dict:
        """
        Recompute features from recent history (simplified rolling computations).
        Matches prepare_features() feature names so model input is consistent.
        """
        s = pd.Series(prices, dtype=float)
        ret_1 = s.pct_change()

        row = {}

        # ret lags (based on ret_1)
        for c in self.feature_cols:
            if c.startswith("ret_lag_"):
                k = int(c.split("_")[-1])
                row[c] = float(ret_1.iloc[-k]) if len(ret_1) > k and pd.notna(ret_1.iloc[-k]) else 0.0

        # MA distance
        for c in self.feature_cols:
            if c.startswith("ma_dist_"):
                w = int(c.split("_")[-1])
                if len(s) >= w:
                    ma = float(s.iloc[-w:].mean())
                    row[c] = float((s.iloc[-1] / ma) - 1.0) if ma != 0 else 0.0
                else:
                    row[c] = 0.0

        # Volatility
        for c in self.feature_cols:
            if c.startswith("vol_"):
                w = int(c.split("_")[-1])
                if len(ret_1.dropna()) >= w:
                    row[c] = float(ret_1.iloc[-w:].std())
                else:
                    row[c] = 0.0

        # Volume-based features
        if volumes is not None:
            v = pd.Series(volumes, dtype=float)
            vol_chg_1 = v.pct_change()
            if "vol_chg_1" in self.feature_cols:
                row["vol_chg_1"] = float(vol_chg_1.iloc[-1]) if pd.notna(vol_chg_1.iloc[-1]) else 0.0
            if "vol_dist_10" in self.feature_cols:
                if len(v) >= 10:
                    roll = float(v.iloc[-10:].mean())
                    row["vol_dist_10"] = float((v.iloc[-1] / roll) - 1.0) if roll != 0 else 0.0
                else:
                    row["vol_dist_10"] = 0.0

        # Ensure all feature columns exist
        for c in self.feature_cols:
            row.setdefault(c, 0.0)

        return row

    # ---------- Signal ----------

    def signal(
        self,
        edge_multiplier: float = 1.0,
    ) -> dict:
        """
        Horizon-aware BUY/HOLD/SELL using:
          - predicted H-day return (direct horizon prediction)
          - model MAE as a confidence/edge gate
          - horizon-scaled thresholds (DEFAULT_HORIZON_THRESHOLDS)
        """
        if not hasattr(self, "horizon"):
            # If someone calls signal() before fit(), default to 5
            self.horizon = 5

        threshold = DEFAULT_HORIZON_THRESHOLDS.get(self.horizon, 0.01)

        metrics = self.evaluate()          # ensures mae exists for this horizon/model
        fc = self.predict_horizon()        # direct H-day forecast (dict)
        pred_ret = float(fc["pred_return"])

        mae = float(metrics.get("mae_return", 0.0))
        edge_ok = abs(pred_ret) >= (edge_multiplier * mae) if mae > 0 else True

        if not edge_ok:
            action = "HOLD"
            note = "Weak signal: predicted move is within typical model error."
        else:
            if pred_ret >= threshold:
                action = "BUY"
                note = f"Expected return exceeds {threshold*100:.1f}% threshold for {self.horizon} trading days."
            elif pred_ret <= -threshold:
                action = "SELL"
                note = f"Expected loss exceeds {threshold*100:.1f}% threshold for {self.horizon} trading days."
            else:
                action = "HOLD"
                note = "Expected return is small relative to horizon thresholds."

        # Signal strength (signed and absolute)
        strength = (pred_ret / mae) if mae > 0 else 0.0
        abs_strength = abs(strength)

        if abs_strength < 1.0:
            strength_label = "weak"
        elif abs_strength < 2.0:
            strength_label = "moderate"
        else:
            strength_label = "strong"

        return {
            "action": action,
            "horizon_days": int(self.horizon),
            "predicted_return": pred_ret,
            "current_price": float(fc["current_price"]),
            "predicted_price": float(fc["pred_price"]),
            "mae_return": mae,
            "threshold_used": threshold,
            "edge_multiplier": edge_multiplier,
            "signal_strength": float(strength),          # signed
            "signal_strength_abs": float(abs_strength),  # magnitude
            "signal_strength_label": strength_label,
            "note": note,
            "model": self.model_name,
            "price_column_used": self.price_col,
        }