import yfinance as yf
import pandas as pd
import talib as tb
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # One level up
sys.path.append(project_root)
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from broker_service import (place_Order)


# ---------------------- MULTI-INDEX SAFE CLEANER ----------------------
def fix_yf_multiindex(df: pd.DataFrame):
    """
    YFinance sometimes returns:
        columns = [('High', ''), ('Low',''), ...] → MultiIndex
    This will ALWAYS fix it into single-level columns.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]   # remove second level
    return df

intervals = {
    "5m":"60d",
    "15m":"60d",
    "1h":"730d"
}
# ---------------------- VOLUME CHECK ----------------------
def volumecheck(data, min_high_vol_candles=2):
    volume = data["Volume"]

    # Normalize → always 1D Series
    if isinstance(volume, pd.DataFrame):
        volume = volume.squeeze()

    if len(volume) < 25:
        return False

    last5 = volume.iloc[-6:-1].astype(float)
    avg20 = float(volume.iloc[-21:-1].mean())

    return (last5 > avg20).sum() > min_high_vol_candles


# ---------------------- SWING HIGH ----------------------
def swingHigh(data, window=2):
    if len(data) < window * 2 + 1:
        return None

    recent = data.iloc[-(window * 2 + 1):]
    mid = window

    mid_high = recent["High"].iloc[mid]
    left_high = recent["High"].iloc[:mid].max()
    right_high = recent["High"].iloc[mid+1:].max()

    if mid_high > left_high and mid_high > right_high:
        return float(mid_high)

    return None


# ---------------------- SWING LOW ----------------------
def swingLow(data, window=2):
    if len(data) < window * 2 + 1:
        return None

    recent = data.iloc[-(window * 2 + 1):]
    mid = window

    mid_low = recent["Low"].iloc[mid]
    left_low = recent["Low"].iloc[:mid].min()
    right_low = recent["Low"].iloc[mid+1:].min()

    if mid_low < left_low and mid_low < right_low:
        return float(mid_low)

    return None


# ====================================================================
#                     LONG (BUY) STRATEGY FUNCTION
# ====================================================================
async def swingLow_volume_trend_rsi_buy(symbol="SBIN", timeframe="15m"):
    try:
        ticker = f"{symbol}.NS"
        interval = intervals[timeframe]
        data = yf.download(ticker, interval=timeframe, period=interval, progress=False)

        if data is None or data.empty:
            print(f"{symbol}: Data empty")
            return

        # Fix MultiIndex columns
        data = fix_yf_multiindex(data)

        # Fix timezone
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            data.index = data.index.tz_convert("Asia/Kolkata")

        currentime =  datetime.now()
        data = data.iloc[:-1]  # remove running candle

        print(f"\n=== {symbol} ===")

        print(data.tail(3))

        # -------- Volume --------
        ok_volume = volumecheck(data)

        # -------- Extract Candle --------
        o = float(data["Open"].iloc[-1])
        c = float(data["Close"].iloc[-1])
        h = float(data["High"].iloc[-1])
        l = float(data["Low"].iloc[-1])

        prev_h = float(data["High"].iloc[-2])
        prev3_h = float(data["High"].iloc[-3])

        # -------- Candle Strength --------
        body = abs(c - o)
        full = h - l
        is_strong = full > 0 and body >= 0.5 * full

        # -------- Indicators --------
        rsi = float(tb.RSI(data["Close"], 14).iloc[-1])
        sma20 = float(tb.SMA(data["Close"], 20).iloc[-1])
        sma50 = float(tb.SMA(data["Close"], 50).iloc[-1])
        sma200 = float(tb.SMA(data["Close"], 200).iloc[-1])

        # Safety
        if any(pd.isna(x) for x in [rsi, sma20, sma50, sma200]):
            print(f"{symbol}: Indicator NaN — skipping")
            return

        # -------- Breakout --------
        is_breakout = (h > prev_h) and (prev_h > prev3_h)

        # -------- Swing Low --------
        sl = swingLow(data)

        signal = False

        # STRATEGY 1
        if (
            sl is not None
            and is_strong
            and sma20 > sma50 > sma200
            and rsi > 50
            and ok_volume
        ):
            signal = True

        # STRATEGY 2
        elif ok_volume and sma50 > sma200 and is_strong and is_breakout:
            signal = True

        if signal:
            # sl  = data['low'].iloc[-3] + 5
            # tp  = c + 10
            place_Order(symbol,2,"B")
            print(f"BUY SIGNAL for {symbol}")
        else:
            print(f"No Buy signal for {symbol}")

    except Exception as e:
        print("Error:", e)

# ====================================================================
#                     SHORT (SELL) STRATEGY FUNCTION
# ====================================================================
async def swingHigh_volume_trend_rsi_buy(symbol="HDFCBANK", timeframe="15m"):
    try:
        ticker = f"{symbol}.NS"
        interval = intervals[timeframe]
        data = yf.download(ticker, interval=timeframe, period=interval, progress=False)

        if data is None or data.empty:
            print(f"{symbol}: Data empty")
            return

        data = fix_yf_multiindex(data)

        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            data.index = data.index.tz_convert("Asia/Kolkata")

        data = data.iloc[:-1]

        print(f"\n=== {symbol} ===")
        print(data.tail(3))

        # -------- Volume --------
        ok_volume = volumecheck(data)

        # -------- Candle --------
        o = float(data["Open"].iloc[-1])
        c = float(data["Close"].iloc[-1])
        h = float(data["High"].iloc[-1])
        l = float(data["Low"].iloc[-1])

        prev_l = float(data["Low"].iloc[-2])
        prev3_l = float(data["Low"].iloc[-3])

        body = abs(c - o)
        full = h - l
        is_strong = full > 0 and body >= 0.5 * full

        # -------- Indicators --------
        rsi = float(tb.RSI(data["Close"], 14).iloc[-1])
        sma20 = float(tb.SMA(data["Close"], 20).iloc[-1])
        sma50 = float(tb.SMA(data["Close"], 50).iloc[-1])
        sma200 = float(tb.SMA(data["Close"], 200).iloc[-1])

        if any(pd.isna(x) for x in [rsi, sma20, sma50, sma200]):
            print(f"{symbol}: Indicator NaN — skipping")
            return

        # -------- Breakout --------
        is_breakout = (l < prev_l) and (prev_l < prev3_l)

        # -------- Swing High --------
        sh = swingHigh(data)

        signal = False

        # STRATEGY 1
        if (
            sh is not None
            and is_strong
            and sma50 < sma200
            and rsi < 50
            and ok_volume
        ):
            signal = True

        # STRATEGY 2
        elif ok_volume and sma50 < sma200 and is_strong and is_breakout:
            signal = True

        if signal:
            # sl  = data['High'].iloc[-3] + 5
            # tp  = c - 10
            place_Order(symbol,2,"S")
            print(f"SELL SIGNAL for {symbol}")
        else:
            print(f"No Sell signal for {symbol}")

    except Exception as e:
        print("Error:", e)


volatile_symbols = [
    "AXISBANK", "INFY", "TCS", "MARUTI",
    "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "ADANIPOWER", "AXISBANK",
    "BAJFINANCE", "BAJAJFINSV", "ULTRACEMCO", "HINDALCO", "ICICIBANK", "BAJAJELEC"
]

uptrend = [ "SBIN", "RELIANCE", "HDFCBANK", "ICICIBANK" , "AXISBANK","ULTRACEMCO"]
downtrend =["AXISBANK", "INFY", "TCS","SBIN", "RELIANCE", "HDFCBANK", "ICICIBANK"]


async def run_all_strategies(timeframe="15m"):
    tasks = []
    for sym in uptrend:

        # BUY strategy
        tasks.append(
            swingLow_volume_trend_rsi_buy(symbol=sym, timeframe=timeframe)
        )

    for sym in downtrend:

        # SELL strategy
        tasks.append(
            swingHigh_volume_trend_rsi_buy(symbol=sym, timeframe=timeframe)
        )

    # Run them concurrently
    print("print time:", datetime.now().strftime("%H:%M:%S"))
    await asyncio.gather(*tasks)


# ============= RUN LOOP =================
# scheduler startup function (unchanged)
async def start_scheduler():
    # asyncio.run(process_queue("15min"))
    await run_all_strategies()
    scheduler = AsyncIOScheduler()
    # scheduler.add_job(process_queue, CronTrigger(second=0), args=["1m"])
    # scheduler.add_job(process_queue, CronTrigger(minute="*/3", second=0), args=["3m"])
    # scheduler.add_job(process_queue, CronTrigger(minute="*/5", second=0), args=["5m"])
    scheduler.add_job(
    lambda loop=asyncio.get_running_loop(): 
        loop.create_task(run_all_strategies("15m")),
    CronTrigger(minute="*/15", second=10)
        )
    
    scheduler.add_job(
        lambda loop=asyncio.get_running_loop():
            loop.create_task(run_all_strategies("1h")),
        CronTrigger(hour="9,10,11,12,13,14,15", minute=15, second=10)
    )

    # scheduler.add_job(process_queue, IntervalTrigger(minutes=60), args=["1h"])
    scheduler.start()
    print(" APScheduler started successfully.")
    await asyncio.Event().wait()
 

if __name__ == "__main__":
    asyncio.run(start_scheduler())
