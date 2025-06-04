from datetime import datetime
import requests
import yfinance as yf
from twelvedata import TDClient

TD_API_KEY = "59076e2930e5489796d3f74ea7082959"
td = TDClient(apikey=TD_API_KEY)

def fetch_latest_price(ticker: str) -> tuple[float, datetime]:
    """
    Fetch the latest price for a stock using the Twelve Data API.
    Returns a tuple: (price, current UTC datetime).
    If the API fails, price will be 0.
    """
    API_KEY = "59076e2930e5489796d3f74ea7082959"
    url = f"https://api.twelvedata.com/price?symbol={ticker}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()
    price = float(data.get("price", 0))
    now = datetime.utcnow()
    return price, now

def fetch_yf_price(ticker: str) -> float:
    """
    Fetch the latest price for a stock using yfinance as a backup.
    Returns the price as a float, or None if not found.
    """
    try:
        data = yf.Ticker(ticker)
        price = data.fast_info['last_price']
        return float(price)
    except Exception:
        return None

def fetch_option_contract_price(ticker: str, expiry_date: str, option_type: str, strike_price: float) -> float:
    """
    Fetch the last price for a specific option contract using yfinance.
    :param ticker: Underlying ticker symbol (e.g., 'AAPL')
    :param expiry_date: Expiry date in 'YYYY-MM-DD' format
    :param option_type: 'Call' or 'Put'
    :param strike_price: Strike price as float
    :return: Last price of the option contract, or None if not found
    """
    try:
        yf_ticker = yf.Ticker(ticker)
        # Get the option chain for the given expiry date
        chain = yf_ticker.option_chain(expiry_date)
        # Select calls or puts DataFrame based on option_type
        options_df = chain.calls if option_type.lower() == "call" else chain.puts
        # Find the row with the exact strike price
        row = options_df[options_df['strike'] == strike_price]
        if not row.empty:
            return float(row.iloc[0]['lastPrice'])
    except Exception as e:
        print(f"Error fetching option price: {e}")
    return None

def fetch_ticker_info(symbol: str) -> dict:
    """
    Fetch detailed information about a ticker symbol using Twelve Data API.
    Returns a dictionary with ticker information.
    """
    try:
        data = td.quote(symbol=symbol).as_json()
        if not data or "code" in data:
            return {}
        return {
            "symbol": data.get("symbol"),
            "name": data.get("name"),
            "last_price": data.get("close"),
            "change": data.get("change"),
            "change_percent": data.get("percent_change"),
            "volume": data.get("volume"),
            "market_cap": None,
            "timestamp": data.get("datetime"),
        }
    except Exception as e:
        print(f"Error fetching ticker info: {e}")
        return {}