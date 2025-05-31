import yfinance as yf
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

class Predictor:

    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.data = self.get_historical_data()

    def get_historical_data(self):
        stock = yf.Ticker(self.ticker)
        data = stock.history(period="1y")
        data.reset_index(inplace=True)
        return data

    def linear_regression_predict(self, days_ahead=5):
        df = self.data.copy()
        df['Day'] = np.arange(len(df))  # simple day index as feature

        X = df[['Day']].values
        y = df['Close'].values

        model = LinearRegression()
        model.fit(X, y)

        future_days = np.arange(len(df), len(df) + days_ahead).reshape(-1, 1)
        predictions = model.predict(future_days)

        return predictions

    def moving_average_predict(self, days_ahead=5, window=10):
        df = self.data.copy()
        df['MA'] = df['Close'].rolling(window=window).mean()

        # Drop NaN values (initial rows that don't have enough data for full window)
        df = df.dropna()

        if len(df) < 2:
            print("Not enough data to calculate slope for Moving Average.")
            return np.full(days_ahead, df['MA'].iloc[-1])

        # Calculate slope: change in MA over last 2 data points
        last_ma = df['MA'].iloc[-1]
        prev_ma = df['MA'].iloc[-2]
        slope = last_ma - prev_ma

        # Project forward
        predictions = []
        for i in range(1, days_ahead + 1):
            predicted_price = last_ma + (slope * i)
            predictions.append(predicted_price)

        return np.array(predictions)

# === Quick test ===
if __name__ == "__main__":
    ticker = input("Enter stock ticker: ").upper()
    model_type = input("Select model (1 = Linear Regression, 2 = Moving Average): ")

    predictor = Predictor(ticker)

    if model_type == "1":
        predictions = predictor.linear_regression_predict()
        print("\nLinear Regression Predictions:")
    else:
        predictions = predictor.moving_average_predict()
        print("\nMoving Average Predictions:")

    for i, price in enumerate(predictions, 1):
        print(f"Day {i}: ${price:.2f}")
