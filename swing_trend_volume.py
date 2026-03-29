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

def is_ema_retest(row, prev_row, tolerance=0.005):

    ema = prev_row["EMA20"]

    # 🟢 BUY (uptrend)
    uptrend = prev_row["Close"] > ema
    touch_up = prev_row["Low"] <= ema
    near_up = abs(prev_row["Close"] - ema) / ema < tolerance
    bounce_up = row["Close"] > row["Open"]

    buy_signal = uptrend and (touch_up or near_up) and bounce_up


    # SELL (downtrend)
    downtrend = prev_row["Close"] < ema
    touch_down = prev_row["High"] >= ema
    near_down = abs(prev_row["Close"] - ema) / ema < tolerance
    bounce_down = row["Close"] < row["Open"]

    sell_signal = downtrend and (touch_down or near_down) and bounce_down

    return buy_signal, sell_signal
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

def check_market_trend(data):
    if len(data) < 200:
        return None

    close = data["Close"]

    ema50 = tb.EMA(close, timeperiod=50)
    ema200 = tb.EMA(close, timeperiod=200)

    ema50_slope = (ema50.iloc[-1] - ema50.iloc[-10]) / ema50.iloc[-10]

    if close.iloc[-1] > ema50.iloc[-1] > ema200.iloc[-1] and ema50_slope > 0.002:
        return "STRONG_UPTREND"

    elif close.iloc[-1] < ema50.iloc[-1] < ema200.iloc[-1] and ema50_slope < -0.002:
        return "STRONG_DOWNTREND"

    else:
        return "SIDEWAYS"
def check_range_market(data, window=50, threshold=0.02):
    if len(data) < window:
        return None

    recent = data[-window:]

    high = recent["High"].max()
    low = recent["Low"].min()

    range_percent = (high - low) / low

    if range_percent < threshold:
        return "RANGE_BOUND"
    
    return "TRENDING"

def check_volatility(data, period=14):
    if len(data) < period:
        return None

    atr = tb.ATR(
        data["High"],
        data["Low"],
        data["Close"],
        timeperiod=period
    )

    current_atr = atr.iloc[-1]
    price = data["Close"].iloc[-1]

    volatility_percent = current_atr / price

    if volatility_percent > 0.02:
        return "HIGH_VOLATILITY"
    elif volatility_percent < 0.01:
        return "LOW_VOLATILITY"
    else:
        return "NORMAL_VOLATILITY"    
def swingLow_volume_trend_rsi_buy(data):
    try:

        # -------- Volume --------
        # ok_volume = volumecheck(data)

        # -------- Extract Candle --------
        # o = float(data["Open"].iloc[-1])
        # c = float(data["Close"].iloc[-1])
        # h = float(data["High"].iloc[-1])
        # l = float(data["Low"].iloc[-1])

        # prev_h = float(data["High"].iloc[-2])
        # prev3_h = float(data["High"].iloc[-3])

        # -------- Candle Strength --------
        # body = abs(c - o)
        # full = h - l
        # is_strong = full > 0 and body >= 0.5 * full

        # -------- Indicators --------
        # rsi = float(tb.RSI(data["Close"], 14).iloc[-1])
        # sma20 = float(tb.SMA(data["Close"], 20).iloc[-1])
        # sma50 = float(tb.SMA(data["Close"], 50).iloc[-1])
        # sma200 = float(tb.SMA(data["Close"], 200).iloc[-1])

        # Safety
        # if any(pd.isna(x) for x in [rsi, sma20, sma50, sma200]):
        #     print(f": Indicator NaN — skipping")
        #     return

        # -------- Breakout --------
        # is_breakout = (h > prev_h) and (prev_h > prev3_h)

        # -------- Swing Low --------
        sl = swingLow(data)

        signal = False

        # STRATEGY 1
        if (
            sl is not None
            # and is_strong
            # and sma50 > sma200
            # and rsi > 55
            # and ok_volume
            # and is_breakout
        ):
            signal = True

        # STRATEGY 2
        # elif ok_volume and sma50 > sma200 and is_strong and is_breakout:
            # signal = True

        # print(signal)    

        if signal:
            # sl  = data['low'].iloc[-3] + 5
            # tp  = c + 10
            return True
        else:
            return False

    except Exception as e:
        print("Error:", e)
        return False

def swingHigh_volume_trend_rsi_buy(data):
    try:
        # -------- Volume --------
        # ok_volume = volumecheck(data)

        # -------- Candle --------
        # o = float(data["Open"].iloc[-1])
        # c = float(data["Close"].iloc[-1])
        # h = float(data["High"].iloc[-1])
        # l = float(data["Low"].iloc[-1])

        # prev_l = float(data["Low"].iloc[-2])
        # prev3_l = float(data["Low"].iloc[-3])

        # body = abs(c - o)
        # full = h - l
        # is_strong = full > 0 and body >= 0.5 * full

        # -------- Indicators --------
        # rsi = float(tb.RSI(data["Close"], 14).iloc[-1])
        # sma20 = float(tb.SMA(data["Close"], 20).iloc[-1])
        # sma50 = float(tb.SMA(data["Close"], 50).iloc[-1])
        # sma200 = float(tb.SMA(data["Close"], 200).iloc[-1])

        # if any(pd.isna(x) for x in [rsi, sma20, sma50, sma200]):
        #     print(f"Indicator NaN — skipping")
        #     return False

        # -------- Breakout --------
        # is_breakout = (l < prev_l) and (prev_l < prev3_l)

        # -------- Swing High --------
        sh = swingHigh(data)

        signal = False

        # STRATEGY 1
        if (
            sh is not None
            # and is_strong
            # and sma50 < sma200
            # and rsi < 50
            # and ok_volume
        ):
            signal =   True


        if signal:
            # sl  =return data['low'].iloc[-3] + 5
            # tp  = c + 10
            return True
        else:
            return False
            
    except Exception as e:
        print("Error:", e)
        return False
    
def generateSignal(dataforTrade, dataForTrend=None):
    if len(dataForTrend) < 50:
       return None


    trend = check_market_trend(dataForTrend)
    dataforTrade["EMA20"] = tb.EMA(dataforTrade["Close"], timeperiod=20)
    row = dataforTrade.iloc[-1]
    prev_row = dataforTrade.iloc[-2]
    
    
    buy_signal, sell_signal = is_ema_retest(row, prev_row)
    
    print(trend)
    print("sell_signal",sell_signal)
    print("buy_signal",buy_signal)

    if buy_signal and trend == "STRONG_UPTREND":
        return "BUY"

    elif sell_signal and trend == "STRONG_DOWNTREND":
        return "SELL"

    return None
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
    
    # scheduler.add_job(
    #     lambda loop=asyncio.get_running_loop():
    #         loop.create_task(run_all_strategies("1h")),
    #     CronTrigger(hour="9,10,11,12,13,14,15", minute=15, second=10)
    # )

    # scheduler.add_job(process_queue, IntervalTrigger(minutes=60), args=["1h"])
    scheduler.start()
    print(" APScheduler started successfully.")
    await asyncio.Event().wait()
 

# if __name__ == "__main__":
#     asyncio.run(start_scheduler())
