from datetime import datetime, timedelta, UTC
import os
import threading
import logging
import requests
import yfinance as yf
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

TD_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

# --- Thread-safe in-memory caches (process-local) ---
_cache_prices_td: Dict[str, Tuple[float, datetime]] = {}
_cache_prices_yf: Dict[str, Tuple[float, datetime]] = {}
_cache_ticker_info: Dict[str, Tuple[dict, datetime]] = {}

# Single reentrant lock guards all three caches
_cache_lock = threading.RLock()

# TTLs
PRICE_TTL = timedelta(seconds=20)
TICKER_INFO_TTL = timedelta(hours=6)

def fetch_latest_price(ticker: str) -> Optional[float]:
    """
    Fetch the latest price for a stock using the Twelve Data API.
    Returns a float or None. Caches for PRICE_TTL.
    """
    now = datetime.now(UTC)
    with _cache_lock:
        hit = _cache_prices_td.get(ticker)
        if hit and now - hit[1] < PRICE_TTL:
            return hit[0]
    if not TD_API_KEY:
        return None
    try:
        url = f"https://api.twelvedata.com/price?symbol={ticker}&apikey={TD_API_KEY}"
        response = requests.get(url, timeout=6)
        response.raise_for_status()
        data = response.json()
        price_raw = data.get("price")
        if price_raw is None:
            return None
        price = float(price_raw)
        with _cache_lock:
            _cache_prices_td[ticker] = (price, now)
        return price
    except Exception:
        return None

def fetch_yf_price(ticker: str) -> Optional[float]:
    """
    Fetch the latest price for a stock using yfinance with multiple fallbacks:
    1) fast_info.last_price
    2) info.regularMarketPrice/currentPrice/previousClose
    3) history(period='1d').Close last
    4) history(period='5d').Close last
    Returns the price as a float, or None if not found.
    """
    now = datetime.now(UTC)
    with _cache_lock:
        hit = _cache_prices_yf.get(ticker)
        if hit and now - hit[1] < PRICE_TTL:
            return hit[0]
    try:
        t = yf.Ticker(ticker)
        # 1) fast_info
        price = None
        try:
            price = (getattr(t, "fast_info", {}) or {}).get("last_price")
        except Exception:
            price = None
        # 2) info fields
        if price is None:
            try:
                info = t.info or {}
                price = (
                    info.get("regularMarketPrice")
                    or info.get("currentPrice")
                    or info.get("previousClose")
                )
            except Exception:
                price = None
        # 3) 1d history close
        if price is None:
            try:
                hist = t.history(period="1d", interval="1d")
                if hasattr(hist, "empty") and not hist.empty:
                    closing = hist["Close"].dropna()
                    if len(closing) > 0:
                        price = float(closing.iloc[-1])
            except Exception:
                price = None
        # 4) 5d history close
        if price is None:
            try:
                hist = t.history(period="5d", interval="1d")
                if hasattr(hist, "empty") and not hist.empty:
                    closing = hist["Close"].dropna()
                    if len(closing) > 0:
                        price = float(closing.iloc[-1])
            except Exception:
                price = None
        if price is None:
            return None
        val = float(price)
        with _cache_lock:
            _cache_prices_yf[ticker] = (val, now)
        return val
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
        logger.debug("Error fetching option price for %s: %s", ticker, e)
    return None

def fetch_ticker_info(symbol: str) -> dict:
    """
    Fetch detailed information about a ticker symbol using Twelve Data's HTTP API.
    Returns a dictionary with ticker information. Caches for TICKER_INFO_TTL.
    Never raises; returns {} on failure or when no API key is configured.
    """
    now = datetime.now(UTC)
    with _cache_lock:
        hit = _cache_ticker_info.get(symbol)
        if hit and now - hit[1] < TICKER_INFO_TTL:
            return hit[0]
    if not TD_API_KEY:
        return {}
    try:
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={TD_API_KEY}"
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        data = resp.json() or {}
        # Twelve Data returns { "code": ..., "message": ... } on errors
        if not data or data.get("code") is not None:
            return {}
        info = {
            "symbol": data.get("symbol"),
            "name": data.get("name"),
            "last_price": data.get("close"),
            "change": data.get("change"),
            "change_percent": data.get("percent_change"),
            "volume": data.get("volume"),
            "market_cap": None,
            "timestamp": data.get("datetime"),
        }
        with _cache_lock:
            _cache_ticker_info[symbol] = (info, now)
        return info
    except Exception:
        return {}