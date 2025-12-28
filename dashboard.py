import streamlit as st
from data_fetcher import DataFetcher
from account import load_cash, save_cash
from predictor import Predictor
import pandas as pd
import csv
import matplotlib.pyplot as plt

def plot_portfolio_pie(portfolio):
    labels = []
    sizes = []

    total_value = 0

    for stock in portfolio:
        fetcher = DataFetcher(stock['ticker'])
        price = fetcher.get_current_price()
        if price is None:
            continue
        stock_value = price * stock['shares']
        labels.append(stock['ticker'])
        sizes.append(stock_value)
        total_value += stock_value

    cash = load_cash()
    if cash > 0:
        labels.append("Cash")
        sizes.append(cash)
        total_value += cash

    fig, ax = plt.subplots(figsize=(6, 4), facecolor="#6D6B6B")
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
    ax.set_title("Portfolio Allocation (by Market Value)")
    st.pyplot(fig)

# Load portfolio
def load_portfolio(filename="portfolio.csv"):
    portfolio = []
    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            portfolio.append({
                'ticker': row['Ticker'],
                'shares': float(row['Shares']),
                'buy_price': float(row['BuyPrice'])
            })
    return portfolio

# Save portfolio
def save_portfolio(portfolio, filename="portfolio.csv"):
    with open(filename, 'w', newline='') as file:
        fieldnames = ['Ticker', 'Shares', 'BuyPrice']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for stock in portfolio:
            writer.writerow({
                'Ticker': stock['ticker'],
                'Shares': stock['shares'],
                'BuyPrice': stock['buy_price']
            })

# Portfolio Summary Display
def display_portfolio():
    portfolio = load_portfolio()
    total_value = 0
    total_cost = 0
    data = []

    for stock in portfolio:
        fetcher = DataFetcher(stock['ticker'])
        price = fetcher.get_current_price()
        stock_value = price * stock['shares']
        cost_basis = stock['shares'] * stock['buy_price']
        gain = stock_value - cost_basis
        gain_pct = (gain / cost_basis) * 100 if cost_basis != 0 else 0

        data.append([stock['ticker'], stock['shares'], f"${price:.2f}", f"${gain:.2f}", f"{gain_pct:.2f}%"])
        total_value += stock_value
        total_cost += cost_basis

    df = pd.DataFrame(data, columns=["Ticker", "Shares", "Current Price", "Gain/Loss", "Gain %"])
    df.index = range(1, len(df) + 1)
    st.table(df)

    total_gain = total_value - total_cost
    st.write(f"**Total Portfolio Value:** ${total_value:.2f}")
    st.write(f"**Total Gain/Loss:** ${total_gain:.2f}")
    st.write(f"**Cash Balance:** ${load_cash():.2f}")
    st.write(f"**Net Worth:** ${total_value + load_cash():.2f}")

    if total_value + load_cash() > 0:
        plot_portfolio_pie(portfolio)

# --- Streamlit App ---

st.set_page_config(page_title="Personal Investment Tracker", layout="wide")

st.sidebar.title("📊 Personal Investment Tracker")

menu = ["📈 Portfolio", "💵 Trade Stocks", "🔮 Predict Stock", "💰 Manage Funds"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "📈 Portfolio":
    st.header("📊 Portfolio Summary")
    display_portfolio()

if choice == "🔮 Predict Stock":
    st.header("🔮 Predict Stock")

    # ========= Inputs =========
    ticker = st.text_input("Ticker", placeholder="e.g., AAPL").strip().upper()

    model_label = st.selectbox("Model", ["Ridge (recommended)", "Linear", "Baseline"])
    model_map = {
        "Ridge (recommended)": "ridge",
        "Linear": "linear",
        "Baseline": "baseline",
    }

    horizon = st.selectbox("Horizon (trading days)", [1, 3, 5, 10, 20], index=2)
    risk_mode = st.selectbox("Risk", ["Conservative", "Normal", "Aggressive"], index=1)

    # Risk affects:
    # 1) horizon threshold strictness (thresh_mult)
    # 2) decision tier cutoffs (tier_cutoffs)
    risk_params = {
        "Conservative": {"thresh_mult": 1.00},
        "Normal":       {"thresh_mult": 0.75},
        "Aggressive":   {"thresh_mult": 0.6},
    }
    thresh_mult = risk_params[risk_mode]["thresh_mult"]

    tier_cutoffs = {
        "Conservative": {"buy": 1.5, "lean": 1.0, "watch": 0.60},
        "Normal":       {"buy": 1.2, "lean": 0.8, "watch": 0.40},
        "Aggressive":   {"buy": 1.0, "lean": 0.6, "watch": 0.30},
    }
    cuts = tier_cutoffs[risk_mode]

    position_type = st.radio("Position input", ["Dollar amount", "Shares"], horizontal=True)
    amount = st.number_input("Amount", min_value=0.0, value=500.0, step=50.0)

    # Session storage for last run (so dropdown changes don't wipe results)
    if "last_pred" not in st.session_state:
        st.session_state.last_pred = None

    run = st.button("Run Prediction", disabled=(ticker == ""))

    # ========= Run model (store results) =========
    if run and ticker:
        try:
            predictor = Predictor(ticker, period="2y", interval="1d")
            predictor.fit(model=model_map[model_label], horizon=horizon, test_size=60, ridge_alpha=1.0)

            metrics = predictor.evaluate()
            fc = predictor.predict_horizon()

            pred_ret = float(fc["pred_return"])
            current_price = float(fc["current_price"])
            pred_price = float(fc["pred_price"])

            mae = float(metrics.get("mae_return", 0.0))
            rmse = float(metrics.get("rmse_return", 0.0))
            dir_acc = float(metrics.get("directional_accuracy", 0.0))

            # ---- thresholds ----
            base_thresholds = {1: 0.003, 3: 0.006, 5: 0.010, 10: 0.020, 20: 0.040}
            base_threshold = base_thresholds.get(horizon, 0.01) * thresh_mult

            mae_based_mult = {
                "Conservative": 1.50,
                "Normal":       1.20,
                "Aggressive":   1.00,
            }[risk_mode]

            min_threshold_floor = 0.001
            threshold = max(min_threshold_floor, min(base_threshold, mae * mae_based_mult))

            edge_score = abs(pred_ret) / mae if mae > 0 else 0.0

            conf_cutoffs = {
                "Conservative": (0.6, 1.2),
                "Normal":       (0.4, 0.9),
                "Aggressive":   (0.3, 0.6),
            }
            low_c, med_c = conf_cutoffs[risk_mode]
            if edge_score < low_c:
                confidence = "Low"
            elif edge_score < med_c:
                confidence = "Med"
            else:
                confidence = "High"

            # ---- decision ----
            if edge_score >= cuts["buy"] and abs(pred_ret) >= threshold:
                decision = "BUY" if pred_ret > 0 else "SELL"
                tag = None
            elif edge_score >= cuts["lean"]:
                decision = "HOLD"
                tag = "Leaning " + ("BUY" if pred_ret > 0 else "SELL")
            elif edge_score >= cuts["watch"]:
                decision = "HOLD"
                tag = "Watchlist"
            else:
                decision = "HOLD"
                tag = "No edge"

            # Save everything needed to re-render without rerunning model
            st.session_state.last_pred = {
                "ticker": ticker,
                "model_label": model_label,
                "horizon": horizon,
                "risk_mode": risk_mode,
                "position_type": position_type,
                "amount": float(amount),
                "metrics": metrics,
                "fc": fc,
                "pred_ret": pred_ret,
                "current_price": current_price,
                "pred_price": pred_price,
                "mae": mae,
                "rmse": rmse,
                "dir_acc": dir_acc,
                "threshold": threshold,
                "edge_score": edge_score,
                "confidence": confidence,
                "decision": decision,
                "tag": tag,
                "raw": predictor.raw.copy(),
                "price_col": predictor.price_col,
            }

        except Exception as e:
            st.error(f"Prediction failed: {e}")

    # ========= Render last prediction (persists through reruns) =========
    saved = st.session_state.last_pred
    if saved is None:
        st.info("Run a prediction to see results.")
    else:
        ticker = saved["ticker"]
        model_label = saved["model_label"]
        horizon = saved["horizon"]
        risk_mode = saved["risk_mode"]
        metrics = saved["metrics"]
        pred_ret = float(saved["pred_ret"])
        current_price = float(saved["current_price"])
        pred_price = float(saved["pred_price"])
        mae = float(saved["mae"])
        rmse = float(saved["rmse"])
        dir_acc = float(saved["dir_acc"])
        threshold = float(saved["threshold"])
        edge_score = float(saved["edge_score"])
        confidence = saved["confidence"]
        decision = saved["decision"]
        tag = saved["tag"]
        raw = saved["raw"]
        price_col = saved["price_col"]

        # ========= Hero decision =========
        if decision == "BUY":
            st.success("✅ BUY")
        elif decision == "SELL":
            st.error("🔴 SELL")
        else:
            st.warning(f"🟡 HOLD — {tag}" if tag else "🟡 HOLD")

        st.caption(f"{ticker} • {horizon}d • {model_label} • {risk_mode}")

        # ========= Key stats row =========
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Expected return", f"{pred_ret*100:.2f}%")
        c2.metric("Strength", f"{edge_score:.2f}", f"Conf: {confidence}")
        c3.metric("MAE", f"±{mae*100:.2f}%")
        c4.metric("Price now", f"${current_price:.2f}")

        st.write(f"**Target price (≈ {horizon} trading days):** ${pred_price:.2f}")

        # ========= Estimated impact =========
        pessimistic = pred_ret - mae
        base = pred_ret
        optimistic = pred_ret + mae

        position_type = saved["position_type"]
        amount = float(saved["amount"])

        def dollar_impact(r: float) -> float:
            if position_type == "Dollar amount":
                return amount * r
            return amount * current_price * r

        impact_df = pd.DataFrame({
            "Scenario": ["Pessimistic", "Base", "Optimistic"],
            "Return": [pessimistic * 100, base * 100, optimistic * 100],
            "Impact": [dollar_impact(pessimistic), dollar_impact(base), dollar_impact(optimistic)],
        })
        impact_df["Return"] = impact_df["Return"].map(lambda x: f"{x:.2f}%")
        impact_df["Impact"] = impact_df["Impact"].map(lambda x: f"${x:.2f}")

        st.subheader("Estimated impact")
        st.table(impact_df)

        with st.expander("Optional stats"):
            s1, s2, s3 = st.columns(3)
            s1.metric("RMSE", f"{rmse:.4f}")
            s2.metric("Directional", f"{dir_acc*100:.1f}%")
            s3.metric("Threshold", f"{threshold*100:.2f}%")

        # ========= Charts =========
        col_title, col_ctrl = st.columns([3, 1])

        with col_title:
            st.subheader("Charts")

        with col_ctrl:
            months_to_show = st.selectbox(
                "Range",
                [6, 12, 24],
                index=1,
                key="chart_months",
                label_visibility="collapsed"
            )

        hist = raw[["Date", price_col]].dropna().copy()
        hist.rename(columns={price_col: "Price"}, inplace=True)
        hist["Date"] = pd.to_datetime(hist["Date"])

        # timezone-safe cutoff
        if getattr(hist["Date"].dt, "tz", None) is not None:
            cutoff_date = pd.Timestamp.now(tz=hist["Date"].dt.tz) - pd.DateOffset(months=months_to_show)
        else:
            cutoff_date = pd.Timestamp.now() - pd.DateOffset(months=months_to_show)

        hist = hist[hist["Date"] >= cutoff_date]

        dates = pd.to_datetime(hist["Date"])
        prices = hist["Price"].astype(float)

        today_date = dates.iloc[-1]
        today_price = float(current_price)

        future_date = pd.bdate_range(today_date + pd.Timedelta(days=1), periods=horizon)[-1]
        target_price = float(pred_price)

        if decision == "BUY" or (decision == "HOLD" and tag and "Leaning BUY" in tag):
            signal_color = "#2ecc71"
        elif decision == "SELL" or (decision == "HOLD" and tag and "Leaning SELL" in tag):
            signal_color = "#e74c3c"
        else:
            signal_color = "#f1c40f"

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(dates, prices, color="#185DA7", linewidth=1.6, alpha=0.85)
        ax.plot([today_date, future_date], [today_price, target_price], color=signal_color, linewidth=1.6)
        ax.scatter(future_date, target_price, s=20, color=signal_color, zorder=5)

        ax.set_title(f"{ticker} — {horizon} trading days")
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.grid(True)

        st.pyplot(fig)    

if choice == "💵 Trade Stocks":
    st.header("💵 Trade Stocks")

    trade_action = st.selectbox("Action", ["Buy", "Sell"])
    ticker = st.text_input("Ticker").upper()
    shares = st.number_input("Shares", min_value=1, step=1)

    if st.button("Execute Trade") and ticker:
        fetcher = DataFetcher(ticker)
        price = fetcher.get_current_price()
        if price is None:
            st.warning("Invalid ticker or failed to fetch price.")
        else:
            total_cost = shares * price
            cash = load_cash()
            portfolio = load_portfolio()

            if trade_action == "Buy":
                if total_cost > cash:
                    st.warning("Insufficient funds! Please deposit money to your portfolio!")
                else:
                    # Update cash
                    cash -= total_cost
                    save_cash(cash)

                    # Update portfolio
                    for stock in portfolio:
                        if stock['ticker'] == ticker:
                            total_shares = stock['shares'] + shares
                            new_avg_price = ((stock['shares'] * stock['buy_price']) + (shares * price)) / total_shares
                            stock['shares'] = total_shares
                            stock['buy_price'] = new_avg_price
                            break
                    else:
                        portfolio.append({
                            'ticker': ticker,
                            'shares': shares,
                            'buy_price': price
                        })
                    save_portfolio(portfolio)
                    st.success(f"Successfully bought {shares} shares of {ticker} at ${price:.2f}")

            elif trade_action == "Sell":
                for stock in portfolio:
                    if stock['ticker'] == ticker:
                        if shares > stock['shares']:
                            st.warning("You don't own that many shares.")
                            break
                        stock['shares'] -= shares
                        cash += shares * price
                        save_cash(cash)

                        if stock['shares'] == 0:
                            portfolio.remove(stock)

                        save_portfolio(portfolio)
                        st.success(f"Successfully sold {shares} shares of {ticker} at ${price:.2f}")
                        break
                else:
                    st.warning("You don't own this stock.")

if choice == "💰 Manage Funds":
    st.header("💰 Manage Cash Balance")
    
    current_cash = load_cash()
    st.write(f"**Current Cash Balance:** ${current_cash:.2f}")

    action = st.selectbox("Action", ["Deposit", "Withdraw"])
    amount = st.number_input("Amount", min_value=0.0, step=1.0)

    if st.button("Submit") and amount > 0:
        if action == "Deposit":
            current_cash += amount
            save_cash(current_cash)
            st.success(f"Deposited ${amount:.2f}. New balance: ${current_cash:.2f}")
        elif action == "Withdraw":
            if amount > current_cash:
                st.warning("Insufficient funds to withdraw.")
            else:
                current_cash -= amount
                save_cash(current_cash)
                st.success(f"Withdrew ${amount:.2f}. New balance: ${current_cash:.2f}")
