import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

# ==============================
# SEASON FUNCTION
# ==============================
def get_season(month):
    if month in [3, 4, 5, 6]:
        return "summer"
    elif month in [7, 8, 9]:
        return "monsoon"
    elif month in [10, 11]:
        return "festive"
    else:
        return "winter"

# ==============================
# DOWNLOAD DATA + ADD SEASON
# ==============================
def get_stock_with_season(symbol):
    df = yf.download(symbol, start="2015-01-01", progress=False).copy()

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["month"] = df.index.month
    df["season"] = df["month"].apply(get_season)

    return df

# ==============================
# STRATEGY (MODIFIED 🔥)
# ==============================
def run_strategy_on_df(df):
    try:
        df = df.copy()

        # EMA
        df["ema50"] = df["Close"].ewm(span=50).mean()
        df["ema200"] = df["Close"].ewm(span=200).mean()

        df["uptrend"] = (df["Close"] > df["ema50"]) & (df["ema50"] > df["ema200"])
        df["downtrend"] = (df["Close"] < df["ema50"]) & (df["ema50"] < df["ema200"])

        # Signals
        df["pullback"] = df["Close"] < df["ema50"]
        df["reclaim"] = df["Close"] > df["ema50"]

        df["buy_signal"] = (
            df["uptrend"] &
            df["pullback"].shift(1) &
            df["reclaim"]
        ).shift(1)

        df["sell_signal"] = (
            df["downtrend"] &
            (df["Close"] > df["ema50"]).shift(1) &
            (df["Close"] < df["ema50"])
        ).shift(1)

        df["buy_signal"] = df["buy_signal"].fillna(0).astype(int)
        df["sell_signal"] = df["sell_signal"].fillna(0).astype(int)

        # Position
        df["position"] = 0
        df.loc[df["buy_signal"] == 1, "position"] = 1
        df.loc[df["sell_signal"] == 1, "position"] = -1
        df["position"] = df["position"].replace(0, np.nan).ffill().fillna(0)

        # ATR
        df["atr"] = (df["High"] - df["Low"]).rolling(14).mean()

        df["entry_price"] = df["Close"].where(df["position"].diff() != 0).ffill()

        df["sl_price"] = np.where(
            df["position"] == 1,
            df["entry_price"] - 2 * df["atr"],
            df["entry_price"] + 2 * df["atr"]
        )

        df["tp_price"] = np.where(
            df["position"] == 1,
            df["entry_price"] + 3 * df["atr"],
            df["entry_price"] - 3 * df["atr"]
        )

        exit_tp = (
            ((df["position"] == 1) & (df["High"] >= df["tp_price"])) |
            ((df["position"] == -1) & (df["Low"] <= df["tp_price"]))
        )

        exit_sl = (
            ((df["position"] == 1) & (df["Low"] <= df["sl_price"])) |
            ((df["position"] == -1) & (df["High"] >= df["sl_price"]))
        )

        df.loc[exit_tp | exit_sl, "position"] = 0
        df["position"] = df["position"].replace(0, np.nan).ffill().fillna(0)

        # Returns
        df["returns"] = df["Close"].pct_change()

        cost = 0.001
        df["trade_change"] = df["position"].diff().abs()

        df["strategy_returns"] = df["position"].shift(1) * df["returns"]
        df["strategy_returns"] -= cost * df["trade_change"]

        df["equity_curve"] = (1 + df["strategy_returns"]).cumprod()

        return df

    except Exception as e:
        print("Error:", e)
        return None

# ==============================
# PERFORMANCE
# ==============================
def calculate_performance(df, initial_capital=1_000_000, symbol="TEST"):
    os.makedirs("backtests", exist_ok=True)

    df = df.copy()

    df["portfolio_value"] = initial_capital * df["equity_curve"]
    final_value = df["portfolio_value"].iloc[-1]

    df["year"] = df.index.year
    yearly_returns = df.groupby("year")["strategy_returns"].apply(
        lambda x: (1 + x).prod() - 1
    )

    years = (df.index[-1] - df.index[0]).days / 365
    cagr = (final_value / initial_capital) ** (1 / years) - 1

    df["peak"] = df["equity_curve"].cummax()
    df["drawdown"] = (df["equity_curve"] - df["peak"]) / df["peak"]
    max_dd = df["drawdown"].min()

    trade_returns = df["strategy_returns"][df["strategy_returns"] != 0]
    win_rate = (trade_returns > 0).mean() if len(trade_returns) > 0 else 0
    
    

    buy_signals = int(df["buy_signal"].sum())
    sell_signals = int(df["sell_signal"].sum())
    total_trades = buy_signals + sell_signals

    def pct(x): return round(x * 100, 2)

    print(f"\n📊 {symbol}")
    print("CAGR:", pct(cagr), "% | DD:", pct(max_dd), "% | WR:", pct(win_rate), "%")

    return {
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),
        "symbol": symbol,
        "cagr": pct(cagr),
        "drawdown": pct(max_dd),
        "winrate": pct(win_rate),
        "trades": total_trades
    }

# ==============================
# 🔥 SEASONAL BACKTEST
# ==============================
def run_seasonal_backtest(symbol):
    df = get_stock_with_season(symbol)

    if df is None:
        return None

    seasons = ["summer", "monsoon", "festive", "winter"]
    results = {}

    for season in seasons:
        df_season = df[df["season"] == season].copy()

        if len(df_season) < 200:
            continue

        strat_df = run_strategy_on_df(df_season)
        perf = calculate_performance(strat_df, symbol=f"{symbol}_{season}")

        results[season] = perf

    return results

# ==============================
# 🔥 RUN MULTIPLE STOCKS
# ==============================
STOCKS = [
    "RELIANCE.NS",
    "TATAMOTORS.NS",
    "VBL.NS",
    "COALINDIA.NS",
    "HAVELLS.NS",
    "UPL.NS"
]

all_results = {}

for stock in STOCKS:
    print(f"\n🚀 Running {stock}")
    res = run_seasonal_backtest(stock)
    
    all_results[stock] = res
    print(f"Results for {stock}:")



os.makedirs("results", exist_ok=True)
with open(f"results/all_seasonal.json", "w") as f:
    json.dump(all_results, f, indent=4)   
print("\n✅ DONE")