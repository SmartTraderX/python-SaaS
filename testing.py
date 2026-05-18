import os
import json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

def pct(x):
    return float(round(float(x) * 100, 2))

import os
import json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

def pct(x):
    return float(round(float(x) * 100, 2))

def runSeasonalPositional(df, entry_months, initial_capital=100000, lookback=20):
    """
    Optimized Seasonal Strategy:
    - Lookback increased to 20 days (1-Month Breakout) to avoid noise.
    - Strict 'One Trade Per Season Window' to completely stop whipsaws.
    - No fixed TP; rides the full seasonal wave using trailing stops.
    """
    if df.empty or len(df) < (lookback + 10):
        return None

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df["current_month"] = df.index.month

    # Technical Indicators (Higher lookback for stronger confirmation)
    df["swing_high"] = df["High"].shift(1).rolling(window=lookback).max()
    df["swing_low"] = df["Low"].shift(1).rolling(window=lookback).min()

    df["trade_pnl"] = 0.0
    position = 0  # 1: Long, -1: Short, 0: Flat
    entry_price = 0.0
    qty = 0.0
    capital = initial_capital
    trailing_stop = 0.0
    
    # Flag to restrict multiple entries in the same seasonal window
    has_traded_this_season = False

    for i in range(len(df)):
        if i < (lookback + 10):
            continue

        current_month = df["current_month"].iloc[i]
        high = df["High"].iloc[i]
        low = df["Low"].iloc[i]
        close = df["Close"].iloc[i]
        
        swing_high = df["swing_high"].iloc[i]
        swing_low = df["swing_low"].iloc[i]

        # Reset seasonal flag when we are outside the trading window
        if current_month not in entry_months:
            has_traded_this_season = False

        # ==========================================
        # 1. LONG POSITION MANAGEMENT
        # ==========================================
        if position == 1:
            if low <= trailing_stop:  # SL Hit
                pnl = (trailing_stop - entry_price) * qty
                df.at[df.index[i], "trade_pnl"] = pnl
                capital += pnl
                position = 0
            elif current_month not in entry_months:  # Season End Force Exit
                pnl = (close - entry_price) * qty
                df.at[df.index[i], "trade_pnl"] = pnl
                capital += pnl
                position = 0
            else:
                trailing_stop = max(trailing_stop, swing_low)  # Trail Stop Loss Up

        # ==========================================
        # 2. SHORT POSITION MANAGEMENT
        # ==========================================
        elif position == -1:
            if high >= trailing_stop:  # SL Hit
                pnl = (entry_price - trailing_stop) * qty
                df.at[df.index[i], "trade_pnl"] = pnl
                capital += pnl
                position = 0
            elif current_month not in entry_months:  # Season End Force Exit
                pnl = (entry_price - close) * qty
                df.at[df.index[i], "trade_pnl"] = pnl
                capital += pnl
                position = 0
            else:
                trailing_stop = min(trailing_stop, swing_high)  # Trail Stop Loss Down

        # ==========================================
        # 3. STRICT SINGLE ENTRY LOGIC
        # ==========================================
        elif position == 0 and current_month in entry_months and not has_traded_this_season:
            if capital > 0:
                # LONG ENTRY: Strong 20-day High Breakout
                if high > swing_high:
                    position = 1
                    entry_price = max(close, swing_high)
                    qty = (capital * 0.95) / entry_price
                    trailing_stop = swing_low
                    has_traded_this_season = True  # Block further trades in this window
                
                # SHORT ENTRY: Strong 20-day Low Breakdown
                elif low < swing_low:
                    position = -1
                    entry_price = min(close, swing_low)
                    qty = (capital * 0.95) / entry_price
                    trailing_stop = swing_high
                    has_traded_this_season = True  # Block further trades in this window

    df["equity_curve"] = (initial_capital + df["trade_pnl"].cumsum()) / initial_capital
    return df

# (Baki ka calculate_performance aur __main__ block purane code jaisa hi rahega)
def calculate_performance(df, symbol, window_name, initial_capital):
    if df is None or df.empty:
        return {}

    final_value = initial_capital * df["equity_curve"].iloc[-1]

    df["peak"] = df["equity_curve"].cummax()
    df["drawdown"] = (df["equity_curve"] - df["peak"]) / df["peak"]
    max_dd = df["drawdown"].min()

    years = (df.index[-1] - df.index[0]).days / 365.25
    if years <= 0:
        years = 1.0

    cagr = (final_value / initial_capital) ** (1 / years) - 1 if final_value > 0 else -1

    trade_returns = df["trade_pnl"][df["trade_pnl"] != 0]
    total_trades = len(trade_returns)
    win_rate = (trade_returns > 0).mean() if total_trades > 0 else 0

    return {
        "symbol": symbol,
        "window": window_name,
        "initial_capital": initial_capital,
        "final_value": float(final_value),
        "cagr": pct(cagr),
        "max_drawdown": pct(max_dd),
        "win_rate": pct(win_rate),
        "total_trades": int(total_trades),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    os.makedirs("backtests", exist_ok=True)

    stocks_list = [
        "VOLTAS.NS", "BLUESTARCO.NS", "HAVELLS.NS", "AMBER.NS", 
        "MARUTI.NS", "TITAN.NS", "KALYANKJIL.NS", "TRENT.NS", 
        "UPL.NS", "PIIND.NS", "COROMANDEL.NS", "BAYERCROP.NS", 
        "ESCORTS.NS", "PAGEIND.NS", "RELAXO.NS", "INDIGO.NS", 
        "IRCTC.NS", "VBL.NS", "TATACONSUM.NS"
    ]

    seasonal_windows = {
        "Jan-Apr (Months 1-4)": [1, 2, 3, 4],
        "May-Aug (Months 5-8)": [5, 6, 7, 8],
        "Sep-Dec (Months 9-12)": [9, 10, 11, 12]
    }

    final_report = {}

    print("--- Running Bi-Directional (Buy/Sell) Seasonal Strategy (10 Years) ---\n")

    for symbol in stocks_list:
        raw_df = yf.download(symbol, start="2016-01-01", progress=False)
        
        if raw_df.empty:
            continue
            
        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        final_report[symbol] = {}
        print(f"========== {symbol} ==========")

        for window_name, months in seasonal_windows.items():
            # Running with lookback=5 days, Target Profit=15%
            result_df = runSeasonalPositional(raw_df, entry_months=months, lookback=5)
            stats = calculate_performance(result_df, symbol, window_name, initial_capital=100000)
            
            final_report[symbol][window_name] = stats
            print(f"  {window_name} -> Trades: {stats['total_trades']} | Win Rate: {stats['win_rate']}% | CAGR: {stats['cagr']}% | MaxDD: {stats['max_drawdown']}%")
        print()

    with open("backtests/bidirectional_seasonal_report.json", "w") as f:
        json.dump(final_report, f, indent=4)
    print("Backtest completed! Bi-directional report saved successfully.")