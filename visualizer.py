import matplotlib.pyplot as plt
from data_fetcher import DataFetcher
from account import load_cash

# --- Portfolio Pie Chart ---

def plot_portfolio_allocation(portfolio):
    labels = []
    sizes = []

    total_value = 0

    # Calculate stock values
    for stock in portfolio:
        fetcher = DataFetcher(stock['ticker'])
        current_price = fetcher.get_current_price()
        if current_price is None:
            continue

        stock_value = stock['shares'] * current_price
        labels.append(stock['ticker'])
        sizes.append(stock_value)
        total_value += stock_value

    # Add cash allocation
    cash = load_cash()
    labels.append("Cash")
    sizes.append(cash)
    total_value += cash

    # Build pie chart
    plt.figure(figsize=(6,6))
    plt.pie(sizes, labels=labels, autopct=lambda p: '{:.1f}%'.format(p) if p > 0 else '', startangle=140)
    plt.title("Total Portfolio Allocation (Market Value + Cash)")
    plt.show()

# --- Prediction Line Chart ---

def plot_prediction(predictions, model_name):
    days = list(range(1, len(predictions)+1))
    plt.figure(figsize=(8,5))
    plt.plot(days, predictions, marker='o')
    plt.title(f"{model_name} Prediction")
    plt.xlabel("Days Ahead")
    plt.ylabel("Predicted Price")
    plt.grid(True)
    plt.show()
