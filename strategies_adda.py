import pandas as pd
import talib as  tb

def volumecheck(data, min_high_vol_candles=2):
    volume = data["Volume"]

    # ALWAYS keep volume 1D
    if isinstance(volume, pd.DataFrame):
        if volume.shape[1] > 1:
            volume = volume.iloc[:, 0]
        else:
            volume = volume.squeeze()

    # Safety
    if len(volume) < 25:
        return False

    last5 = volume.iloc[-6:-1]
    average20 = volume.iloc[-21:-1].mean()

    # Convert everything to numpy float
    last5 = last5.astype(float).values
    average20 = float(average20)

    count = (last5 > average20).sum()

    return count > min_high_vol_candles


def smaRejection(data, smavalue):
    # --- Basic validation ---
    if data is None or len(data) < 3 or smavalue is None:
        return False

    first = data["Close"].iloc[-1]
    second = data["Close"].iloc[-2]
    third = data["Close"].iloc[-3]

    # Rejection logic:
    # Pehli 2 candles SMA ke upar ho sakti hai
    # Last candle SMA ke niche close ho → bearish rejection
    if (third > smavalue or second > smavalue) and first < smavalue:
        return True
    
    return False


def sma_rejection(data):
    if data is None or len(data) < 200:
        print("Data is Empty or insufficient candles")
        return False

    # --- Candle values ---
    o = float(data["Open"].iloc[-1])
    c = float(data["Close"].iloc[-1])
    h = float(data["High"].iloc[-1])
    l = float(data["Low"].iloc[-1])

    # --- Indicators ---
    sma20 = tb.SMA(data["Close"], 20)
    sma50 = tb.SMA(data["Close"], 50)
    sma200 = tb.SMA(data["Close"], 200)

    sma20_last = float(sma20.iloc[-1])
    sma50_last = float(sma50.iloc[-1])
    sma200_last = float(sma200.iloc[-1])

    # Indicator NaN check
    if pd.isna(sma20_last) or pd.isna(sma50_last) or pd.isna(sma200_last):
        print("Indicators are null – skipping candle")
        return False

    # --- Trend check ---
    downtrend = sma20_last < sma50_last < sma200_last

    # --- Rejection check ---
    rejection = smaRejection(data=data, smavalue=sma20_last)

    # --- Volume spike ---
    vol_spike = volumecheck(data)

    # --- Bearish candle strength ---
    body = abs(c - o)
    full = h - l
    strong_bear = (body >= 0.5 * full) and (c < o)

    # Final Signal
    signal = downtrend and rejection and vol_spike and strong_bear
    return signal

    


        


   



