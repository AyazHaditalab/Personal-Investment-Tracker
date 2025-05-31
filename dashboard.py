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
    st.header("🔮 Stock Price Prediction")

    ticker = st.text_input("Enter Stock Ticker:")
    model = st.selectbox("Model", ["Linear Regression", "Moving Average"])

    if st.button("Run Prediction") and ticker:
        predictor = Predictor(ticker)
        if model == "Linear Regression":
            predictions = predictor.linear_regression_predict()
        else:
            predictions = predictor.moving_average_predict()

        for i, price in enumerate(predictions, 1):
            st.write(f"Day {i}: ${price:.2f}")

        # Plot predictions
        fig, ax = plt.subplots(figsize=(6, 4), facecolor="#6D6B6B")
        ax.plot(range(1, len(predictions) + 1), predictions, marker='o')
        ax.set_title(f"{model} Predictions for {ticker}")
        ax.set_xlabel("Days Ahead")
        ax.set_ylabel("Predicted Price")
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
