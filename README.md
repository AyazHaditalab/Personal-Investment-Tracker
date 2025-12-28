# Personal Investment Tracker & Stock Predictor (Streamlit)

A full-featured personal finance and investment tracker built entirely in Python, with an interactive Streamlit web interface and persistent SQL-backed storage.

This project simulates a realistic retail investing platform: users can manage a virtual portfolio, trade stocks using live market data, track performance over time, and generate risk-aware, multi-day stock predictions using machine learning.

---

## 🚀 Features

- Interactive Streamlit dashboard
- Real-time stock prices via yfinance
- Persistent portfolio storage using SQLite
- Transaction-based accounting system
- Portfolio tracking with:
  - Total portfolio value
  - Cash balance
  - Unrealized gains/losses
  - Net worth
- Buy & sell stocks at live prices (simulation)
- Virtual cash account (deposit / withdraw)
- Portfolio allocation visualization (stocks + cash)
- Profit-over-time chart (excluding deposits/withdrawals)
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

## 🗄️ Data Storage Design

Portfolio state is **not stored directly**.

Instead, the system uses a **transaction ledger model**, similar to real brokerages:

- Every buy, sell, deposit, and withdrawal is recorded as a transaction
- Current holdings and cash balance are computed from transaction history
- Portfolio performance over time is reconstructed from historical prices

### Benefits:
- Full auditability of all actions
- Accurate profit calculation excluding cash inflows/outflows
- Clean separation between data persistence and analytics logic
- New users start with a clean database on first run

SQLite is used for simplicity and portability, with all database logic implemented in Python.

---

## 🛠️ Tech Stack

- Python 3
- Streamlit — Web UI
- SQLite — Persistent storage / Database layer
- yfinance — Market data
- pandas — Data manipulation
- numpy — Numerical computation
- scikit-learn — Machine learning
- matplotlib — Data visualization
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
On first run, a fresh local SQLite database will be created automatically.

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

- Portfolio allocation chart (stocks + cash)
- Historical price chart
- Profit-over-time chart (cash-neutral)
- Decision-colored forecast line
- Target price projection for selected horizon
---

## 🎯 Skills Demonstrated

- End-to-end Python application development
- SQL-backend data persistence and schema design
- Transaction-based financial accounting
- Financial data ingestion & processing
- Feature engineering for time-series prediction
- Machine learning model implementation
- Risk-adjusted decision systems
- UI/UX design for analytical dashboards
- Resume-grade project architecture

---

## ⚠️ Disclaimer

This project is for educational/analytical purposes only.  
It does not provide professional financial advice or investment recommendations.

---

## 👤 Author

Ayaz Haditalab  
Honours Mathematics Co-op Student  
University of Waterloo

---

## 📌 Project Status

This project is considered feature-complete.

Optional future extensions:
- Additional technical indicators
- Multi-user support
- Cloud deployment
