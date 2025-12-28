# Personal Investment Tracker & Stock Predictor (Streamlit)

A full-featured personal finance and investment tracker built entirely in Python, with an interactive Streamlit web interface.

This project simulates a realistic retail investing platform: users can manage a virtual portfolio, trade stocks using live market data, track performance, and generate risk-aware, multi-day stock predictions using machine learning.

---

## 🚀 Features

- Interactive Streamlit dashboard
- Real-time stock prices via yfinance
- Portfolio tracking with:
  - Total value
  - Cash balance
  - Unrealized gains/losses
  - Net worth
- Buy & sell stocks at live prices (simulation)
- Virtual cash account (deposit / withdraw)
- Portfolio allocation pie chart (stocks + cash)
- Multi-day stock prediction engine with:
  - Ridge Regression (default)
  - Linear Regression
  - Baseline (no-skill) model
- Risk-aware decision logic:
  - BUY / SELL / HOLD
  - Leaning Buy / Sell
  - Watchlist / No edge
- Volatility-adaptive thresholds
- Confidence & signal strength scoring
- Clean charts with decision-colored signals

---

## 🧠 Prediction Philosophy

This project intentionally avoids unrealistic “always buy” signals.

Signals are only shown when:
- Predicted return exceeds typical model error (MAE)
- Market volatility justifies an edge
- Selected risk tolerance allows it

As a result:
- BUY / SELL signals are uncommon
- HOLD is the most common outcome
- This mirrors real-world quantitative finance behavior

---

## 🛠️ Tech Stack

- Python 3
- Streamlit — Web UI
- yfinance — Market data
- pandas — Data manipulation
- numpy — Numerical computation
- scikit-learn — Machine learning
- matplotlib — Data visualization
- CSV — Lightweight persistence
- VS Code — Development environment

---

## 📦 Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```
### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```
---

## ▶️ Running the App

### Streamlit GUI (recommended)
```bash
streamlit run dashboard.py
```
The app will open automatically in your browser.

## 📂 App Sections

- 📈 Portfolio  
  View holdings, gains/losses, allocation, and net worth.

- 💵 Trade Stocks  
  Buy and sell stocks using real-time prices and a virtual balance.

- 🔮 Predict Stock  
  Generate multi-day forecasts with risk-aware BUY / SELL / HOLD decisions.

- 💰 Manage Funds  
  Deposit or withdraw virtual cash.

---

## 📊 Visualizations

- Portfolio allocation pie chart
- Historical price chart
- Decision-colored forecast line
- Target price projection for selected horizon

---

## 🎯 Skills Demonstrated

- End-to-end Python application development
- Financial data ingestion & processing
- Feature engineering for time-series prediction
- Machine learning model implementation
- Risk-adjusted decision systems
- UI/UX design for analytical tools
- Resume-grade project architecture

---

## ⚠️ Disclaimer

This project is for educational purposes only.  
It does not provide financial advice or investment recommendations.

---

## 👤 Author

Ayaz Haditalab  
Honours Mathematics Co-op Student  
University of Waterloo

---

## ⬆️ Pushing Updates to GitHub
```bash
git status
git add .
git commit -m "Finalize Streamlit investment tracker and prediction system"
git push origin main
```
If your default branch is master:
```bash
git push origin master
```
---

## 📌 Project Status

This project is considered feature-complete.

Optional future extensions:
- Strategy backtesting
- Additional technical indicators
- Exportable reports (CSV / PDF)
- Multi-user support
- Cloud deployment
