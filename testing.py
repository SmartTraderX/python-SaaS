import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

def get_season(month):
    if month in [3, 4, 5, 6]:
        return "summer"
    elif month in [7, 8, 9]:
        return "monsoon"
    elif month in [10, 11]:
        return "festive"
    else:
        return "winter"

def get_season(month):
    if month in [3, 4, 5]:
        return "summer"
    elif month in [6, 7, 8, 9]:
        return "monsoon"
    elif month in [10]:
        return "festive"
    else:
        return "winter"


def get_seasonal_data(symbol):
    # 1. Download data
    df = yf.download(symbol, start="2015-01-01", progress=False).copy()

    if df.empty:
        return None

    # 2. Fix MultiIndex issue (if any)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 3. Add symbol column
    df["symbol"] = symbol

    # 4. Create month + season
    df["month"] = df.index.month
    df["season"] = df["month"].apply(get_season)

    # 5. Prepare final output
    season_data = {
        "summer": df[df["season"] == "summer"].drop(columns=["month", "season"]).copy(),
        "monsoon": df[df["season"] == "monsoon"].drop(columns=["month", "season"]).copy(),
        "festive": df[df["season"] == "festive"].drop(columns=["month", "season"]).copy(),
        "winter": df[df["season"] == "winter"].drop(columns=["month", "season"]).copy(),
    }

    return season_data

def convert_lightweight(data):
    json_data = {}

    for season, df in data.items():
        temp = df.reset_index()[["Date", "Close"]]
        json_data[season] = temp.to_dict(orient="records")

    return json_data



def runStrategy(df):
    
    initial_capital = 100000
    risk_per_trade = 0.02  # 2%
    
    if df.empty:
        print("DataFrame is empty. Cannot run strategy.")
        return None
    
    window = 5
    
    # Calculate swing highs and lows
  # Calculate swing highs and lows (non-repainting basic version)

    df["swing_high"] = (
        (df["High"] > df["High"].shift(1)) &
        (df["High"] > df["High"].shift(2))
    )

    df["swing_low"] = (
        (df["Low"] < df["Low"].shift(1)) &
        (df["Low"] < df["Low"].shift(2))
    )

    # Mark the actual swing points
    df["last_swing_high"] = np.where(df["swing_high"], df["High"], np.nan)
    df["last_swing_low"]  = np.where(df["swing_low"], df["Low"], np.nan)
    
    # Forward fill the last swing points to use them for BOS detection
    df["last_swing_high"] = df["last_swing_high"].ffill()
    df["last_swing_low"] = df["last_swing_low"].ffill()
    
    # Detect Break of Structure (BOS)
    df["bos"] = df["Close"] > df["last_swing_high"]
    df["bos_down"] = df["Close"] < df["last_swing_low"]
    
    # Calculate the range of the candle
    df["range"] = (df["High"] - df["Low"]) / df["Close"]
    df["range_ok"] = df["range"] > 0.01   # 1% move minimum
    
    
    # Generate buy/sell signals based on BOS and range
    df["buy_signal"] = (df["bos"] & df["range_ok"]).shift(1)  # Buy on the next candle after BOS up
    df["sell_signal"] = (df["bos_down"] & df["range_ok"]).shift(1)  # Sell on the next candle after BOS down
    
    # Clean up signals
    df["buy_signal"] = df["buy_signal"].fillna(0).astype(int)
    df["sell_signal"] = df["sell_signal"].fillna(0).astype(int)
    
    df["risk_amount"] = initial_capital * risk_per_trade

    df["qty"] = df["risk_amount"] / (df["entry_price"] * 0.01)
    
    df["position"] = 0

    # Set position based on signals
    df.loc[df["buy_signal"] == 1, "position"] = 1
    df.loc[df["sell_signal"] == 1, "position"] = -1
    df["position"] = df["position"].replace(0,np.nan).ffill().fillna(0)


    df["entry_price"] = df["Close"].where(df["position"].diff() != 0).ffill()
    df["position_value"] = df["qty"] * df["entry_price"]
    
    
    df["sl_price"] = np.where(df["position"] == 1, df["entry_price"] * 0.99)  # 1% stop loss for long
    df["tp_price"] = np.where(df["position"] == 1, df["entry_price"] * 1.02)  # 2% take profit for long
    
    
    
    
    

    
    # json_data = convert_lightweight(data)

# with open("seasonal_data.json", "w") as f:
#     json.dump(json_data, f, indent=4)           