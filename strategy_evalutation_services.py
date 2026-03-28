import sys
import os
import numpy as np
import pandas as pd
import talib as  tb
from datetime import datetime
import uuid
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # One level up
sys.path.append(project_root)
from strategies_adda import sma_rejection
from swing_trend_volume import generateSignal
import uuid
import yfinance as yf

os.makedirs("results",exist_ok=True)

# from app.services.paper_trade_service import (create_paper_Order)
# from app.services.strategy_service import (mark_symbol_match)
# from app.models.strategy_model import Strategy
# from app.logger import logger
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


def saveInJson(results):
    import json
    symbolname = "SBIN"
    with open(f"results/NSE_HDFCBANK-EQ_15.json","w") as f:
        json.dump({"results":results},f ,indent=4)
        print("save succesfully")

def calculate_metrics(backtestResults, equity_curve, initial_capital):

    winning_pnl = sum(t["pnl"] for t in backtestResults if t["pnl"] > 0)
    losing_pnl = sum(t["pnl"] for t in backtestResults if t["pnl"] < 0)

    winning_trades = len([t for t in backtestResults if t["pnl"] > 0])
    losing_trades = len([t for t in backtestResults if t["pnl"] < 0])

    total_trades = len(backtestResults)

    avg_win = winning_pnl / winning_trades if winning_trades else 0
    avg_loss = losing_pnl / losing_trades if losing_trades else 0

    profit_factor = winning_pnl / abs(losing_pnl) if losing_pnl != 0 else 0
    risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    win_rate = (winning_trades / total_trades) if total_trades else 0
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    equity = pd.Series(equity_curve)
    drawdown = (equity - equity.cummax()) / equity.cummax()
    max_drawdown = abs(drawdown.min() * 100)
    

    return {
        "initial_capital": initial_capital,
        "final_capital": round(equity.iloc[-1], 2),

        "max_drawdown": max_drawdown,

        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,

        "win_rate": round(win_rate * 100, 2),

        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),

        "profit_factor": round(profit_factor, 2),
        "risk_reward": round(risk_reward, 2),
        "expectancy": round(expectancy, 2),
    }

def calculate_atr(data, period=14):
    high = data["High"]
    low = data["Low"]
    close = data["Close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()

    return atr

def create_position(signal, price, data, capital, risk_percent,atr):

    risk_amount = capital * risk_percent

    # atr = data["ATR"].iloc[-1]
   
#    Base benchmark bana  Isko baseline maan
#     SL = 1.5 ATR
#     TP = 2 ATR
#     RR ≈ 1.33

    # BUY
    if signal == "BUY":
        sl = price - (1.5 * atr)
        tp = None
        sl_points = price - sl

    # SELL
    elif signal == "SELL":
        sl = price + (2 * atr)
        tp = None
        sl_points = sl - price

    else:
        return None

    if sl_points <= 0:
        return None

    qty = int(risk_amount / sl_points)

    if qty <= 0:
        return None

    return {
        "id": str(uuid.uuid4()),
        "type": signal,
        "qty": qty,
        "entry_price": price,
        "sl_price": sl,
        "tp_price": tp,
        "atr":atr
    }
def update_trailing_sl(pos, current_price, atr):

    if pos["type"] == "BUY":

        if current_price > pos["entry_price"] + (1.5 * atr):

            new_sl = current_price - (1.5 * atr)

            if new_sl > pos["sl_price"]:
                pos["sl_price"] = new_sl

    elif pos["type"] == "SELL":

        if current_price < pos["entry_price"] - (1.5 * atr):

            new_sl = current_price + (1.5 * atr)

            if new_sl < pos["sl_price"]:
                pos["sl_price"] = new_sl

    return pos

def move_to_cost(pos, current_price, atr):

    if pos["type"] == "BUY":
        if current_price > pos["entry_price"] + (1 * atr):
            pos["sl_price"] = max(pos["sl_price"], pos["entry_price"])

    elif pos["type"] == "SELL":
        if current_price < pos["entry_price"] - (1 * atr):
            pos["sl_price"] = min(pos["sl_price"], pos["entry_price"])

    return pos
def check_exit(pos, high, low):

    # BUY position
    if pos["type"] == "BUY":
        if low <= pos["sl_price"]:
            pnl = (pos["sl_price"] - pos["entry_price"]) * pos["qty"]
            return True, pnl, "SL Hit"

    # SELL position
    elif pos["type"] == "SELL":
        if high >= pos["sl_price"]:
            pnl = (pos["entry_price"] - pos["sl_price"]) * pos["qty"]
            return True, pnl, "SL Hit"

    return False, 0, None  

def Backtest_Worker_Testing_sync(symbolName):
    try:
        print(f"🔹 {symbolName}: Worker started")

        data = pd.read_parquet("NSE_HDFCBANK-EQ_15.parquet")
        data_1h = pd.read_parquet("60_data/NSE_HDFCBANK-EQ_60.parquet")
        data = data.set_index(pd.to_datetime(data["datetime"]))
        data_1h = data_1h.set_index(pd.to_datetime(data_1h["datetime"]))

        # print(data.head())

        if data is None or data.empty:
            raise ValueError("No data returned")

        data = fix_yf_multiindex(data)

        # ---- Timezone fix ----
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

        if data_1h.index.tz is None:
            data_1h.index = data_1h.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
            
        data["ATR"] = calculate_atr(data)
        os.makedirs("Atrs",exist_ok=True)
        pd.DataFrame(data["ATR"]).to_json("Atrs/atr.json", orient="records",indent=4)
        capital = 100000.0
        MAX_POSITIONS = 3
        risk_percent = 0.01
        risk_per_trade = risk_percent / MAX_POSITIONS
        positions = []
        backtestResults = []
        equity_curve = []
        equity_curve.append(100000)
        signal_count = 0

        start_index = 50
        
        # for idx in range(start_index, len(data)):
            
        #     equity_curve.append(capital)
        #     newData = data.iloc[:idx]
        #     currentTime = newData.index[-1]
        #     close_price = float(data["Open"].iloc[idx])   # next candle entry

        #     newdata_60h = data_1h[data_1h.index <= currentTime]
        #     if newdata_60h.empty:
        #         continue

        #     signal = generateSignal(newData, newdata_60h)
            
        #     # ENTRY
        #     new_pos = create_position(signal, close_price, newData, capital, risk_per_trade)

        #     if new_pos and len(positions) < MAX_POSITIONS:
        #         new_pos["entry_time"] = str(currentTime)
        #         positions.append(new_pos)
        #         signal_count += 1

        #     # EXIT
        #     high = float(data["High"].iloc[idx])
        #     low = float(data["Low"].iloc[idx])

        #     active_positions = []
        #     current_price = float(data["Close"].iloc[idx])
        #     current_atr = data["ATR"].iloc[idx]

        #     for pos in positions:
        #         pos = update_trailing_sl(pos, current_price, pos["atr"])
        #         pos = move_to_cost(pos, current_price, pos["atr"])
        #         closed, pnl, reason = check_exit(pos, high, low)

        #         if closed:
        #             capital += pnl
        #             pos["pnl"] = pnl
        #             pos["exit_time"] = str(currentTime)
        #             pos["exit_reason"] = reason

        #             backtestResults.append(pos)
        #             equity_curve.append(capital)
        #         else:
        #             active_positions.append(pos)

        #     positions = active_positions

        # # ===== METRICS =====
        # metrics = calculate_metrics(backtestResults, equity_curve, 100000)
        # yearly_return = {}
        # year_start_capital = 100000  # reset
                
        # df = pd.DataFrame(backtestResults)
        # df["exit_time"] = pd.to_datetime(df["exit_time"])
        # df["year"] = df["exit_time"].dt.year
        # yearly_pnl = df.groupby("year")["pnl"].sum()


        # for year, pnl in yearly_pnl.items():
        #     pct = (pnl / year_start_capital) * 100
        #     yearly_return[year] = round(pct, 2)
        #     year_start_capital += pnl

        # # print(yearly_return)
        
        


        # print(f"{symbolName}: Done | Trades={len(backtestResults)} | Capital={capital:.2f}")
        # return {
        #     "symbol": symbolName,
        #     "yearly_return":yearly_return,
        #     "metrices": metrics,
        #     "trades": list(reversed(backtestResults))
        # }

    except Exception as e:
        print(f" {symbolName}: Error -> {e}")
        return {
            "symbol": symbolName,
            "error": str(e),
            "metrices": {},
            "trades": []
        }
if __name__ == "__main__":

    results = Backtest_Worker_Testing_sync("HDFCBANK")
    saveInJson(results)
    print(results)
    
    # data = pd.read_parquet("60_data/NSE_HDFCBANK-EQ_60.parquet")
    # print(len(data))
    # print(data)
    
    

    # data = getIntradayData("SBIN" , "15m")

    # result = volumecheck(data)

    # print(result)