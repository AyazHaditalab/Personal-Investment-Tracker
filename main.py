import csv
from data_fetcher import DataFetcher
from predictor import Predictor
from visualizer import plot_prediction
from visualizer import plot_portfolio_allocation
from account import load_cash, save_cash

# =============================
# Portfolio Loader/Saver
# =============================

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

# =============================
# Menu Loop
# =============================

def main_menu():
    while True:
        print("\n====== Personal Investment Tracker ======")
        print("1. View Portfolio")
        print("2. Deposit Funds")
        print("3. Withdraw Funds")
        print("4. Buy Stock")
        print("5. Sell Stock")
        print("6. Run Prediction")
        print("7. Exit")

        choice = input("Select an option: ")

        if choice == "1":
            portfolio = load_portfolio()
            view_portfolio(portfolio)
        elif choice == "2":
            deposit_funds()
        elif choice == "3":
            withdraw_funds()
        elif choice == "4":
            buy_stock()
        elif choice == "5":
            sell_stock()
        elif choice == "6":
            run_prediction()
        elif choice == "7":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

# =============================
# Placeholder functions
# =============================

def view_portfolio(portfolio):
    print("\n=== Portfolio Summary ===")
    total_value = 0
    total_cost = 0

    for stock in portfolio:
        fetcher = DataFetcher(stock['ticker'])
        current_price = fetcher.get_current_price()
        if current_price is None:
            print(f"Could not fetch price for {stock['ticker']}")
            continue

        stock_value = stock['shares'] * current_price
        cost_basis = stock['shares'] * stock['buy_price']
        gain = stock_value - cost_basis
        gain_pct = (gain / cost_basis) * 100

        total_value += stock_value
        total_cost += cost_basis

        print(f"Ticker: {stock['ticker']}")
        print(f"  Shares: {stock['shares']}")
        print(f"  Buy Price: ${stock['buy_price']:.2f}")
        print(f"  Current Price: ${current_price:.2f}")
        print(f"  Gain/Loss: ${gain:.2f} ({gain_pct:.2f}%)")
        print("---------------------------")

    total_gain = total_value - total_cost
    total_gain_pct = (total_gain / total_cost) * 100 if total_cost != 0 else 0

    print("======== Overall Portfolio ========")
    print(f"Total Portfolio Value: ${total_value:.2f}")
    print(f"Total Gain/Loss: ${total_gain:.2f} ({total_gain_pct:.2f}%)")

    cash = load_cash()
    print(f"Cash Balance: ${cash:.2f}")
    print(f"Net Worth (Cash + Stocks): ${total_value + cash:.2f}")

    plot_portfolio_allocation(portfolio)

def run_prediction():
    ticker = input("Enter stock ticker to predict: ").upper()
    predictor = Predictor(ticker)

    print("Select model:")
    print("1. Linear Regression")
    print("2. Moving Average")

    model_choice = input("Enter choice: ")

    if model_choice == "1":
        predictions = predictor.linear_regression_predict()
        print("\nLinear Regression Predictions:")
        model_name = "Linear Regression"
    else:
        predictions = predictor.moving_average_predict()
        print("\nMoving Average Predictions:")
        model_name = "Moving Average"

    for i, price in enumerate(predictions, 1):
        print(f"Day {i}: ${price:.2f}")

    # Plot predictions visually
    plot_prediction(predictions, model_name)

def deposit_funds():
    cash = load_cash()
    print(f"\nCurrent balance: ${cash:.2f}")
    amount = float(input("Enter deposit amount: "))
    if amount <= 0:
        print("Invalid deposit amount.")
        return
    cash += amount
    save_cash(cash)
    print(f"Deposit successful. New balance: ${cash:.2f}")

def withdraw_funds():
    cash = load_cash()
    print(f"\nCurrent balance: ${cash:.2f}")
    amount = float(input("Enter withdrawal amount: "))
    if amount <= 0 or amount > cash:
        print("Invalid withdrawal amount.")
        return
    cash -= amount
    save_cash(cash)
    print(f"Withdrawal successful. New balance: ${cash:.2f}")

def buy_stock():
    ticker = input("Enter stock ticker to buy: ").upper()
    shares = float(input("Enter number of shares to buy: "))

    if shares <= 0:
        print("Invalid number of shares.")
        return

    fetcher = DataFetcher(ticker)
    current_price = fetcher.get_current_price()

    if current_price is None:
        print(f"Could not fetch price for {ticker}")
        return

    total_cost = shares * current_price
    cash = load_cash()

    print(f"Current price: ${current_price:.2f}")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Available cash: ${cash:.2f}")

    if total_cost > cash:
        print("Insufficient funds! Please deposit money to your portfolio!")
        return

    # Deduct cash
    cash -= total_cost
    save_cash(cash)

    # Load current portfolio
    portfolio = load_portfolio()

    # Check if stock already exists
    for stock in portfolio:
        if stock['ticker'] == ticker:
            total_shares = stock['shares'] + shares
            new_avg_price = ((stock['shares'] * stock['buy_price']) + (shares * current_price)) / total_shares
            stock['shares'] = total_shares
            stock['buy_price'] = new_avg_price
            break
    else:
        # New stock entry
        portfolio.append({
            'ticker': ticker,
            'shares': shares,
            'buy_price': current_price
        })

    # Save updated portfolio
    save_portfolio(portfolio)

    print(f"Successfully bought {shares} shares of {ticker} at ${current_price:.2f}")

def sell_stock():
    portfolio = load_portfolio()
    ticker = input("Enter stock ticker to sell: ").upper()
    shares_to_sell = float(input("Enter number of shares to sell: "))

    if shares_to_sell <= 0:
        print("Invalid number of shares.")
        return

    for stock in portfolio:
        if stock['ticker'] == ticker:
            if shares_to_sell > stock['shares']:
                print("You don't own that many shares.")
                return

            fetcher = DataFetcher(ticker)
            current_price = fetcher.get_current_price()

            if current_price is None:
                print(f"Could not fetch price for {ticker}")
                return

            total_sale = shares_to_sell * current_price
            stock['shares'] -= shares_to_sell

            if stock['shares'] == 0:
                portfolio.remove(stock)

            cash = load_cash()
            cash += total_sale
            save_cash(cash)
            save_portfolio(portfolio)

            print(f"Sold {shares_to_sell} shares of {ticker} at ${current_price:.2f}")
            print(f"Total sale: ${total_sale:.2f}")
            return

    print(f"You don't own any shares of {ticker}.")

# =============================

if __name__ == "__main__":
    main_menu()
