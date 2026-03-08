import operator
import sys
import os
import numpy as np
import pandas as pd
import talib as  tb
import yfinance as yf
import asyncio
from datetime import datetime
import uuid
import logging
import threading
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # One level up
sys.path.append(project_root)
from strategies_adda import sma_rejection
from swing_trend_volume import swingLow_volume_trend_rsi_buy
import uuid
import yfinance as yf

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
strategy = {
  "_id": "690767bade68b5e0109817c1",
  "userId": None,
  "strategyName": "Testing strategy",
  "category": "Swing",
  "description": "testing ",
  "timeframe": "15m",
  "status": False,
  "associatedBroker": None,
  "createdBy": None,
  "createdAt": "2025-11-02T19:05:08.732000",
  "expiryDate": "2025-11-09T19:05:08.732000",
  "orderDetails": {
    "action": "BUY",
    "symbol": [
    #     {
    #     "id": "690767bade68b5e0109817bf",
    #     "name": "TCS",
    #     "theStrategyMatch": False,
    #     "symbolCode": "3045"
    #   },
    #   {
    #     "id": "690767bade68b5e0109817bf",
    #     "name": "HDFCBANK",
    #     "theStrategyMatch": False,
    #     "symbolCode": "3045"
    #   },
    #     {
    #     "id": "690767bade68b5e0109817bf",
    #     "name": "AXISBANK",
    #     "theStrategyMatch": False,
    #     "symbolCode": "3045"
    #   },
      {
        "id": "690767bade68b5e0109817c0",
        "name": "TCS",
        "theStrategyMatch": False,
        "symbolCode": "2885"
      }
    ]
  },
  "tags": [],
  "totalSubscriber": []
}
uptrend = [ "SBIN", "RELIANCE", "HDFCBANK", "ICICIBANK"]
downtrend =["AXISBANK", "INFY", "TCS","SBIN", "RELIANCE", "HDFCBANK", "ICICIBANK"]

def saveInJson(results):
    import json
    symbolname = "SBIN"
    with open(f"result_{symbolname}.json","w") as f:
        json.dump({"results":results},f ,indent=4)
        print("save succesfully")


def Backtest_Worker_Testing_sync(symbolName, strategy):
    try:
        print(f"🔹 {symbolName}: Worker started")

        data = pd.read_csv("data.csv", parse_dates=["datetime"])
        data.set_index("datetime", inplace=True)

        print(data.head())

        if data is None or data.empty:
            raise ValueError("No data returned")

        data = fix_yf_multiindex(data)

        # ---- Timezone fix ----
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            data.index = data.index.tz_convert("Asia/Kolkata")

        capital = 100000.0
        risk_percent = 0.01

        positions = []
        backtestResults = []

        winning_pnl = losing_pnl = 0.0
        winning_trades = losing_trades = 0
        signal_count = 0

        start_index = 50

        # ================= LOOP =================
        for idx in range(start_index, len(data)):

            if capital <= 0:
                print(f"🛑 {symbolName}: Capital exhausted.")
                break

            newData = data.iloc[:idx]

            close_price = float(newData["Close"].iloc[-1])
            currentTime = newData.index[-1]

            # ===== ENTRY =====
            signal = swingLow_volume_trend_rsi_buy(newData)

            if signal:

                risk_amount = capital * risk_percent

                entry_price = close_price

                sl_price = float(newData["Low"].iloc[-3]) - 7
                tp_price = entry_price + 15

                sl_points = entry_price - sl_price

                if sl_points <= 0:
                    continue

                quantity = int(risk_amount / sl_points)

                if quantity <= 0:
                    print(f"🛑 {symbolName}: Capital too low")
                    break

                signal_count += 1

                positions.append({
                    "id": str(uuid.uuid4()),
                    "type": "BUY",
                    "qty": quantity,
                    "entry_price": entry_price,
                    "entry_time": str(currentTime),
                    "sl_price": sl_price,
                    "tp_price": tp_price
                })

            # ===== EXIT =====
            active_positions = []

            high = float(newData["High"].iloc[-1])
            low = float(newData["Low"].iloc[-1])

            for pos in positions:

                closed = False

                # TP
                if high >= pos["tp_price"]:
                    pnl = (pos["tp_price"] - pos["entry_price"]) * pos["qty"]
                    reason = "TP Hit"
                    closed = True

                # SL
                elif low <= pos["sl_price"]:
                    pnl = (pos["sl_price"] - pos["entry_price"]) * pos["qty"]
                    reason = "SL Hit"
                    closed = True

                if closed:

                    capital += pnl

                    pos.update({
                        "exit_price": close_price,
                        "exit_time": str(currentTime),
                        "exit_reason": reason,
                        "pnl": round(pnl, 2),
                        "capital_after_trade": round(capital, 2)
                    })

                    backtestResults.append(pos)

                    if pnl > 0:
                        winning_trades += 1
                        winning_pnl += pnl
                    else:
                        losing_trades += 1
                        losing_pnl += pnl

                else:
                    active_positions.append(pos)

            positions = active_positions

        # ===== METRICS =====
        total_trades = len(backtestResults)

        metrices = {
            "initial_capital": 100000,
            "final_capital": round(capital, 2),
            "total_trades": total_trades,
            "signal_count": signal_count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "winning_pnl": round(winning_pnl, 2),
            "losing_pnl": round(losing_pnl, 2),
            "total_pnl": round(winning_pnl + losing_pnl, 2),
            "win_rate": round(
                (winning_trades / total_trades) * 100, 2
            ) if total_trades else 0.0
        }

        print(f"✅ {symbolName}: Done | Trades={total_trades} | Final Capital={capital:.2f}")

        return {
            "symbol": symbolName,
            "metrices": metrices,
            "trades": list(reversed(backtestResults))
        }

    except Exception as e:
        print(f"❌ {symbolName}: Error -> {e}")
        return {
            "symbol": symbolName,
            "error": str(e),
            "metrices": {},
            "trades": []
        }
if __name__ == "__main__":

    results = Backtest_Worker_Testing_sync("ICICIBANK",strategy)
    saveInJson(results)
    print(results)

    # data = getIntradayData("SBIN" , "15m")

    # result = volumecheck(data)

    # print(result)