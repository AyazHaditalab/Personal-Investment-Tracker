import yfinance as yf

class DataFetcher:
    def __init__(self, ticker):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)

    def get_current_price(self):
        data = self.stock.history(period="1d")
        if not data.empty:
            return data['Close'].iloc[-1]
        else:
            return None

    def get_company_info(self):
        info = self.stock.info
        return {
            'shortName': info.get('shortName'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'marketCap': info.get('marketCap'),
            'currency': info.get('currency')
        }

    def get_historical_data(self, period="1y"):
        data = self.stock.history(period=period)
        return data
