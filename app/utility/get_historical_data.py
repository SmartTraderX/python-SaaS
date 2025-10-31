import yfinance as yf
import pandas as pd

def nse_to_yfinance(symbol: str) -> str:
    """Convert NSE symbol to yfinance-compatible ticker."""
    return f"{symbol.upper()}.NS"

def getIntradayData(symbol: str, interval: str ="1m", period: str = "7d"):
    # print(f"Fetching data for: {symbol}")
    
    ticker = nse_to_yfinance(symbol)
    # print(ticker)

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
        
        # ✅ Flatten MultiIndex columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        print(f"✅ Data fetched successfully for {symbol}")
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
        data.index = data.index.tz_localize('UTC').tz_convert('Asia/Kolkata')

        print(f"✅ Data fetched successfully for {symbol}. Total candles: {len(data)}")
        return data

    except Exception as e:
        print(f"⚠️ Error fetching data for {symbol}: {e}")
        return None


# Example usage
# ticker = "RELIANCE"
# data = getHistoricalData(ticker, interval="1d", period="5y")

# if data is not None:
#     print("\nLast Completed Candle:")
#     print(data)


#     print("💾 Saved to data.csv")





# | Interval | Period Max | Ek din me bars (NSE approx) | Purpose               |
# | -------- | ---------- | --------------------------- | --------------------- |
# | `1m`     | 7d         | 375                         | Scalping / short-term |
# | `2m`     | 60d        | 187                         | Intraday              |
# | `5m`     | 60d        | 75                          | Intraday / backtest   |
# | `15m`    | 60d        | 25                          | Swing                 |
# | `1h`     | 730d       | 6                           | Swing / EOD           |
# | `1d`     | Max years  | 1                           | Daily strategy        |