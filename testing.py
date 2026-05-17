import os
import json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

def pct(x):
    return float(round(float(x) * 100, 2))

def runSeasonalPositional(df, entry_months, initial_capital=100000, risk_per_trade=0.05):
    """
    Pure Seasonal Positional Strategy:
    - Enters a position at the start of the peak season.
    - Uses a wider 5% Stop Loss to survive market noise.
    - NO target profit; rides the entire season wave.
    - Forcibly exits when the season ends.
    """
    if df.empty or len(df) < 5:
        return None

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df["current_month"] = df.index.month

    df["trade_pnl"] = 0.0
    position = 0  # 1: In Trade, 0: Flat
    entry_price = 0.0
    qty = 0.0
    capital = initial_capital

    for i in range(len(df)):
        current_month = df["current_month"].iloc[i]
        high = df["High"].iloc[i]
        low = df["Low"].iloc[i]
        close = df["Close"].iloc[i]

        # 1. EXIT LOGIC (If we are holding a stock)
        if position == 1:
            # Rule A: Stop Loss Hit (5% Drop from Entry)
            if low <= entry_price * 0.95:
                pnl = (entry_price * 0.95 - entry_price) * qty
                df.at[df.index[i], "trade_pnl"] = pnl
                capital += pnl
                position = 0
            
            # Rule B: Season Ends -> Force Square-off at Closing Price
            elif current_month not in entry_months:
                pnl = (close - entry_price) * qty
                df.at[df.index[i], "trade_pnl"] = pnl
                capital += pnl
                position = 0

        # 2. ENTRY LOGIC (If we are flat and a new season window opens)
        # We enter if the month is correct AND the previous day wasn't already in the season (Season Start)
        elif position == 0 and current_month in entry_months:
            # Safety check to ensure we only enter at the START of the season, not every single day
            if i > 0 and df["current_month"].iloc[i-1] not in entry_months:
                if capital > 0:  # Protect against going negative
                    position = 1
                    entry_price = close
                    # Deploying 95% of current capital into the stock for positional delivery
                    qty = (capital * 0.95) / entry_price 

    # Re-calculate equity curve based on actual accounted capital
    df["equity_curve"] = (initial_capital + df["trade_pnl"].cumsum()) / initial_capital
    return df

def calculate_performance(df, symbol, initial_capital):
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
        "initial_capital": initial_capital,
        "final_value": float(final_value),
        "cagr": pct(cagr),
        "max_drawdown": pct(max_dd),
        "win_rate": pct(win_rate),
        "total_trades": int(total_trades),
        "timestamp": datetime.now().isoformat()
    }

# ==========================================
# RUNNING THE NEW SYSTEM
# ==========================================
if __name__ == "__main__":
    os.makedirs("backtests", exist_ok=True)

    # Specific Stocks mapped to their structural Peak Seasons
    seasonal_baskets = {
        "VOLTAS.NS": [3, 4, 5, 6],       # Summer (March - June)
        "HAVELLS.NS": [3, 4, 5, 6],      # Summer (March - June)
        "MARUTI.NS": [9, 10, 11],        # Festive (Sept - Nov)
        "TITAN.NS": [10, 11, 12, 1],     # Festive & Wedding (Oct - Jan)
        "COROMANDEL.NS": [6, 7, 8, 9]    # Monsoon/Agri (June - Sept)
    }

    final_report = {}

    print("--- Running Pure Seasonal Positional Holding (2015 - Present) ---\n")

    for symbol, peak_months in seasonal_baskets.items():
        raw_df = yf.download(symbol, start="2015-01-01", progress=False)
        
        if raw_df.empty:
            continue
            
        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        # Run the new positional logic
        result_df = runSeasonalPositional(raw_df, entry_months=peak_months)
        stats = calculate_performance(result_df, symbol, initial_capital=100000)
        final_report[symbol] = stats
        
        print(f"{symbol} -> Trades: {stats['total_trades']} | Win Rate: {stats['win_rate']}% | CAGR: {stats['cagr']}% | MaxDD: {stats['max_drawdown']}%")

    # Save to JSON
    with open("backtests/positional_seasonal_report.json", "w") as f:
        json.dump(final_report, f, indent=4)
        