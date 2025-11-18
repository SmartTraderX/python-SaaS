import yfinance as yf
import pandas as pd
import os
import sys

# Make app folder visible for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from app.scheduler.broker_scheduler import login_smartapi
from datetime import datetime, timedelta

def nse_to_yfinance(symbol: str) -> str:
    """Convert NSE symbol to yfinance-compatible ticker."""
    return f"{symbol.upper()}.NS"


timeframes = {
    "1m": "7d",      # 1-minute data -> max 7 days
    "2m": "60d",     # 2-minute data -> max 60 days
    "5m": "60d",     # 5-minute data -> max 60 days
    "15m": "60d",    # 15-minute data -> max 60 days
    "1h": "730d",    # 1-hour data -> ~2 years
    "1d": "5y",      # 1-day data -> 5 years
}

def get_return_days(interval: str) -> str:
    """
    Returns maximum lookback period for given Yahoo Finance interval.
    Raises ValueError if interval is unsupported.
    """
    if interval not in timeframes:
        raise ValueError(f"Unsupported interval '{interval}'. Choose from: {list(timeframes.keys())}")
    return timeframes[interval]


def getIntradayData(symbol: str, interval: str):
    # print(f"Fetching data for: {symbol}")
    
    ticker = nse_to_yfinance(symbol)

    # print(ticker)
    period = get_return_days(interval)

    try:
        data = yf.download(
            tickers=ticker,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=True
        )

        if data is None or data.empty:
            print(f"❌ No data fetched for {symbol}")
            return None
        
        # Flatten MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        print(f"Data fetched successfully for {symbol}")
        return data

    except Exception as e:
        print(f"⚠️ Error fetching data for {symbol}: {e}")
        return None


def getHistoricalData(symbol: str, interval: str ="1d", period: str = "5y"):
    print(f"📊 Fetching data for: {symbol}")

    # Convert NSE symbol to yfinance format
    ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    try:
        data = yf.download(
            tickers=ticker,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=True
        )

        if data is None or data.empty:
            print(f"❌ No data fetched for {symbol}")
            return None

        # Flatten MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        # Convert to Indian timezone
        if data.index.tz is None:
          data.index = data.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
        else:
            data.index = data.index.tz_convert('Asia/Kolkata')


        print(f"Data fetched successfully for {symbol}. Total candles: {len(data)}")
        return data

    except Exception as e:
        print(f"⚠️ Error fetching data for {symbol}: {e}")
        return None

import asyncio

def login_smartapi_sync():
    try:
        return asyncio.run(login_smartapi())
    except RuntimeError:
        # Handle case where there's already a running event loop (like in FastAPI)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return loop.create_task(login_smartapi())
        else:
            return loop.run_until_complete(login_smartapi())

def getIntradayDataFromSmartAPi(symbol: str, interval: str):
    try:
        # convert user interval to SmartAPI-compatible
        interval_map = {
            "1m": "ONE_MINUTE",
            "3m": "THREE_MINUTE",
            "5m": "FIVE_MINUTE",
            "10m": "TEN_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "30m": "THIRTY_MINUTE",
            "1h": "ONE_HOUR",
            "1d": "ONE_DAY",
        }
        candle_interval = interval_map.get(interval, "FIVE_MINUTE")

        # 🔹 SmartAPI expects symbol_token and exchange
        # You can pre-map symbols → tokens for faster lookup
        # Example: NIFTY index or RELIANCE
        token_map = {
            "NIFTY": ("26000", "NSE"),
            "BANKNIFTY": ("26009", "NSE"),
            "RELIANCE": ("2885", "NSE"),
            "SBIN": ("3045", "NSE")
        }

        if symbol not in token_map:
            print(f"⚠️ Symbol not found in token map: {symbol}")
            return None

        symbol_token, exchange = token_map[symbol]

        tokens = login_smartapi_sync()
        obj = tokens["obj"]
        feedToken = tokens["feedToken"]

        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)  # intraday = 7 days max allowed

        params = {
            "exchange": exchange,
            "symboltoken": symbol_token,
            "interval": candle_interval,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M"),
        }

        historic_data = obj.getCandleData(params)
        candles = historic_data.get("data")

        if not candles:
            print(f"❌ No data fetched for {symbol}")
            return None

        # 🧹 Convert to DataFrame
        df = pd.DataFrame(candles, columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        df.set_index("Datetime", inplace=True)

        print(f"✅ Data fetched successfully for {symbol} ({interval})")
        return df

    except Exception as e:
        print(f"⚠️ Error fetching data for {symbol}: {e}")
        return None




# # Example usage
# ticker = "SBIN"
# data = getHistoricalData(ticker, interval="5m", period="7d")

# if data is not None and not data.empty:
#     print("\nLast Completed Candle:")
#     print(data)
#     data.to_csv("SBI_1h.csv", index=False)
# else:
#     print("No data available to save.")

#     print("💾 Saved to data.csv")







# | Interval | Period Max | Ek din me bars (NSE approx) | Purpose               |
# | -------- | ---------- | --------------------------- | --------------------- |
# | `1m`     | 7d         | 375                         | Scalping / short-term |
# | `2m`     | 60d        | 187                         | Intraday              |
# | `5m`     | 60d        | 75                          | Intraday / backtest   |
# | `15m`    | 60d        | 25                          | Swing                 |
# | `1h`     | 730d       | 6                           | Swing / EOD           |
# | `1d`     | Max years  | 1                           | Daily strategy        |