import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor , as_completed
# ==============================
# 1. LOAD DATA
# # ==============================
# def run_strategy(symbol):
#     try:
#         df = yf.download(symbol, start="2017-01-01", end=datetime.today(), progress=False)

#         if df.empty:
#             print(f"{symbol} ❌ No Data")
#             return None

#         # Fix columns
#         if isinstance(df.columns, pd.MultiIndex):
#             df.columns = df.columns.get_level_values(0)

#         # ==============================
#         # SWING
#         # ==============================
#         window = 5
#         df["swing_high"] = df["High"] == df["High"].rolling(window).max()
#         df["swing_low"]  = df["Low"]  == df["Low"].rolling(window).min()

#         df["last_swing_high"] = np.where(df["swing_high"], df["High"], np.nan)
#         df["last_swing_low"]  = np.where(df["swing_low"], df["Low"], np.nan)

#         df["last_swing_high"] = df["last_swing_high"].ffill()
#         df["last_swing_low"]  = df["last_swing_low"].ffill()

#         # ==============================
#         # MODERN ENTRY 🔥
#         # ==============================
#         df["bos"] = df["Close"] > df["last_swing_high"]
        
#         df["range"] = (df["High"] - df["Low"]) / df["Close"]

#         df["range_ok"] = df["range"] > 0.01   # 1% move minimum
#         # df["momentum"] = df["Close"].pct_change(3)

#         df["buy_signal"] = (
#             df["bos"] &
#             (df["Close"].shift(1) <= df["last_swing_high"].shift(1)) 
#             & df["range_ok"]
#             # (df["momentum"] > 0.02)
#         )
        
#         df["bos_down"] = df["Close"] < df["last_swing_low"]
        
#         df["sell_signal"] = (
#             (df["Close"] < df["last_swing_low"]) &
#             (df["Close"].shift(1) >= df["last_swing_low"].shift(1))  & # 🔥 fresh breakdown
#             df["range_ok"]
#         )
#         df["buy_signal"] = df["buy_signal"].astype(int)
#         df["sell_signal"] = df["sell_signal"].astype(int)

#         # ==============================
#         # POSITION
#         # ==============================
#         df["position"] = 0
#         df.loc[df["buy_signal"] == 1, "position"] = 1
#         df.loc[df["sell_signal"] == 1, "position"] = -1
#         df["position"] = df["position"].replace(0, np.nan).ffill().fillna(0)

#         # ==============================
#         # TP / SL
#         # ==============================
#         tp_pct = 0.04
#         sl_pct = 0.02

#         df["trade_change"] = df["position"].diff()

#         df["entry_price"] = df["Close"].where(df["trade_change"] != 0)
#         df["entry_price"] = df["entry_price"].ffill()

#         df["tp_price"] = np.where(
#             df["position"] == 1,
#             df["entry_price"] * (1 + tp_pct),
#             df["entry_price"] * (1 - tp_pct)
#         )

#         df["sl_price"] = np.where(
#             df["position"] == 1,
#             df["entry_price"] * (1 - sl_pct),
#             df["entry_price"] * (1 + sl_pct)
#         )

#         exit_tp = (
#             ((df["position"] == 1) & (df["Close"] >= df["tp_price"])) |
#             ((df["position"] == -1) & (df["Close"] <= df["tp_price"]))
#         )

#         exit_sl = (
#             ((df["position"] == 1) & (df["Close"] <= df["sl_price"])) |
#             ((df["position"] == -1) & (df["Close"] >= df["sl_price"]))
#         )

#         df.loc[exit_tp | exit_sl, "position"] = 0

#         # ==============================
#         # RETURNS
#         # ==============================
#         df["returns"] = df["Close"].pct_change()
#         df["strategy_returns"] = df["position"].shift(1) * df["returns"]
#         df["equity_curve"] = (1 + df["strategy_returns"]).cumprod()

#         final_value = df["equity_curve"].iloc[-1]
        
#         print(f"{symbol} ✅ Final Value: {round(final_value, 2)}")

#         return df

#     except Exception as e:
#         print(f"{symbol} ❌ Error: {e}")
#         return None

# # ==============================
# # PERFORMANCE FUNCTION (same as yours)
# ==============================
def run_strategy(symbol):
    try:
        df = yf.download(symbol, start="2017-01-01", progress=False)

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ==============================
        # TREND (CORE EDGE)
        # ==============================
        df["ema50"] = df["Close"].ewm(span=50).mean()
        df["ema200"] = df["Close"].ewm(span=200).mean()

        df["uptrend"] = (df["Close"] > df["ema50"]) & (df["ema50"] > df["ema200"])
        df["downtrend"] = (df["Close"] < df["ema50"]) & (df["ema50"] < df["ema200"])

        # ==============================
        # PULLBACK ENTRY (SMART ENTRY)
        # ==============================
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

        # ==============================
        # POSITION
        # ==============================
        df["position"] = 0
        df.loc[df["buy_signal"] == 1, "position"] = 1
        df.loc[df["sell_signal"] == 1, "position"] = -1
        df["position"] = df["position"].replace(0, np.nan).ffill().fillna(0)

        # ==============================
        # ATR STOP (SMART SL)
        # ==============================
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

        # ==============================
        # RETURNS
        # ==============================
        df["returns"] = df["Close"].pct_change()

        cost = 0.001
        df["trade_change"] = df["position"].diff().abs()

        df["strategy_returns"] = df["position"].shift(1) * df["returns"]
        df["strategy_returns"] -= cost * df["trade_change"]

        df["equity_curve"] = (1 + df["strategy_returns"]).cumprod()

        return df

    except:
        return None
def calculate_performance(df, initial_capital=10_00_000, symbol="HDFCBANK.NS"):
    
    
    os.makedirs("backtests", exist_ok=True)

    df = df.copy()

    # ==============================
    # Portfolio Value
    # ==============================
    df["portfolio_value"] = initial_capital * df["equity_curve"]
    final_value = df["portfolio_value"].iloc[-1]

    # ==============================
    # Year-wise Returns
    # ==============================
    df["year"] = df.index.year
    yearly_returns = df.groupby("year")["strategy_returns"].apply(
        lambda x: (1 + x).prod() - 1
    )

    # ==============================
    # CAGR
    # ==============================
    years = (df.index[-1] - df.index[0]).days / 365
    cagr = (final_value / initial_capital) ** (1 / years) - 1

    # ==============================
    # Drawdown
    # ==============================
    df["peak"] = df["equity_curve"].cummax()
    df["drawdown"] = (df["equity_curve"] - df["peak"]) / df["peak"]
    max_dd = df["drawdown"].min()

    # ==============================
    # Win Rate
    # ==============================
    trade_returns = df["strategy_returns"][df["strategy_returns"] != 0]

    win_rate = (trade_returns > 0).mean() if len(trade_returns) > 0 else 0

    total_trades = int(df["buy_signal"].sum())

    # ==============================
    # FORMAT FUNCTIONS 🔥
    # ==============================
    def pct(x):
        return round(x * 100, 2)

    # ==============================
    # PRINT RESULTS
    # ==============================
    print("\n====== PERFORMANCE ======")
    print("Initial Capital:", initial_capital)
    print("Final Value:", round(final_value, 2))
    print("Total Trades:", total_trades)
    print("CAGR:", pct(cagr), "%")
    print("Max Drawdown:", pct(max_dd), "%")
    print("Win Rate:", pct(win_rate), "%")
    print("========================")
    
    

    print("\nYear-wise Returns (%):")
    print(yearly_returns.mul(100).round(2))

    # ==============================
    # SAVE RESULTS
    # ==============================
    

  

    result = {
        "symbol": symbol,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        # Capital
        "initial_capital": initial_capital,
        "final_value": round(final_value, 2),

        # RAW VALUES (for calc)
        "cagr_raw": float(cagr),
        "max_drawdown_raw": float(max_dd),
        "win_rate_raw": float(win_rate),

        # FORMATTED (for display) 🔥
        "cagr_percent": pct(cagr),
        "max_drawdown_percent": pct(max_dd),
        "win_rate_percent": pct(win_rate),

        "total_trades": total_trades,

        # yearly returns both formats
        "yearly_returns_raw": yearly_returns.to_dict(),
        "yearly_returns_percent": {
            str(year): pct(val) for year, val in yearly_returns.items()
        }
    }
    
    

    # Save JSON
    filename = f"backtests/{symbol}_cagr_{pct(cagr)}.json"
    with open(filename, "w") as f:
        json.dump(result, f, indent=4)
        
    filename = f"reports/{symbol}_cagr_{pct(cagr)}.json"
    with open(filename, "w") as f:
        json.dump(result, f, indent=4)    

    # Save CSV
    df.to_csv(f"backtests/{symbol}_data.csv")

    print(f"\n✅ Saved JSON: {filename}")
    print(f"✅ Saved CSV: backtests/{symbol}_data.csv")

    return {
    "symbol": symbol,
    "cagr": float(cagr),
    "final_value": float(final_value),
    "max_drawdown": float(max_dd),
    "win_rate": float(win_rate),
    "trades": int(total_trades)
}
# ==============================
# CALL FUNCTION
# ==============================

symbols = [
    "HDFCBANK.NS",
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "ICICIBANK.NS",
    "ADANIENT.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS",
    "SBIN.NS",
    "LT.NS"
]


finalResult = []
with ThreadPoolExecutor(max_workers=5) as executor:
    
    future_to_symbol = {
        executor.submit(run_strategy, sym): sym for sym in symbols
    }

    for future in as_completed(future_to_symbol):
        symbol = future_to_symbol[future]

        try:
            df = future.result()

            if df is not None:
                result = calculate_performance(
                    df,
                    initial_capital=10_00_000,
                    symbol=symbol
                )
                finalResult.append(result)
                

        except Exception as e:
            print(f"{symbol} ❌ Failed: {e}")
            
            
os.makedirs("reports", exist_ok=True)
with open("reports/final_results.json", "w") as f:
    json.dump(finalResult, f, indent=4)            