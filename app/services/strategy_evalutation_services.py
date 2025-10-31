import operator
import sys
import os
import numpy as np
import pandas as pd
import talib as  tb
import asyncio
import logging
import threading
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # One level up
sys.path.append(project_root)
from utility.get_historical_data import getIntradayData , getHistoricalData
from app.services.paper_trade_service import (create_paper_Order)

logger = logging.getLogger(__name__)

class NumberNode:
    def __init__(self , value):
        self.value = value

    def __repr__(self):
        return f'Number({self.value})'
    
    def evaluate(self, candle):
        return float(self.value)

class IndicatorNode:
    def __init__(self , name , params=None , field=None , data = None , timeframe = None):
        self.name = name
        self.params = params or []
        self.field = field
        self.data = data
        self.timeframe = timeframe
    
    def __repr__(self):
        return f'{self.name}({",".join(map(str , self.params))})' if self.params else self.name
    
    def evaluate(self):
        val = None
        if self.name.lower() == "volume":
            val = float(self.data['Volume'].iloc[-1])

        elif self.name.lower() in ["sma"]:
            period = int( self.params.get("period", 20) if isinstance(self.params, dict) else 20)
            val = float(tb.SMA(self.data['Close'], timeperiod=period).iloc[-1])    
        elif self.name.lower() in ["sma-volume"]:
            period = int(self.params.get("period", 20) if isinstance(self.params, dict) else 20)
            val = float(tb.SMA(self.data['Volume'], timeperiod=period).iloc[-1])
        elif self.name.lower() == "macd-macd":
            macd, signal, hist = tb.MACD(
                self.data['Close'],
                fastperiod= int(self.params.get("fast", 12)),
                slowperiod=int(self.params.get("slow", 26)),
                signalperiod=self.params.get("signal", 9)
            )
            val = float(macd.iloc[-1])
        elif self.name.lower() == "macd-signal":
            macd, signal, hist = tb.MACD(
                self.data['Close'],
                fastperiod=self.params.get("fast", 12),
                slowperiod=self.params.get("slow", 26),
                signalperiod=self.params.get("signal", 9)
            )
            val = float(signal.iloc[-1])

        # print(f"Evaluating {self.name}: {val}")
        return val

class ComparatorNode:
    OPS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }

    def __init__(self , left , op , right):
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f'({self.left} {self.op} {self.right})'
    
    def evaluate(self):
        left_val = self.left.evaluate()
        right_val = self.right.evaluate()
        # print('left',left_val)
        # print('right',right_val)
        return self.OPS[self.op](left_val, right_val)

class LogicalNode:
    def __init__(self , left , op , right):
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f'({self.left} {self.op} {self.right})'
    
    def evaluate(self):

        if self.op == "AND":
            # print('print-left',self.left)
            # print('print-right',self.right)
            return self.left.evaluate() and self.right.evaluate()
        elif self.op == "OR":
            return self.left.evaluate() or self.right.evaluate()
        else:
            raise ValueError(f"Unknown logical operator {self.op}")
# ---------------- Test -------------------
def convertInNodes(expression , data):

    exp1 = expression[0]
    op = expression[1]["name"]
    exp2 = expression[2]
    left =IndicatorNode(exp1.get('name') ,exp1.get('params'),exp1.get('field'),data)
    right =IndicatorNode(exp2.get('name') ,exp2.get('params'),exp2.get('field') , data)

    return ComparatorNode(left, op, right)

def parsedCondition(conditions ,data):
    if len(conditions) == 3 and conditions[1]['type'] == "condition":
       return convertInNodes(conditions ,data)
     
    for idx , con in enumerate(conditions):
        if con['type'] == "logicalOperator":
            op = con['name'].upper()
            left = parsedCondition(conditions[:idx] , data)
            right = parsedCondition(conditions[idx+1:] , data)
            return LogicalNode(left ,op,right)
    # fallback
    return None

def worker(symbolName, strategy, results, lock, paper_Trade, main_loop):
    """
    Worker function for evaluating a strategy and optionally creating a paper trade.
    main_loop: the asyncio event loop from the main thread
    """
    try:
        # Extract strategy info
        timeframe = strategy.timeframe
        condition = strategy.condition

        # Get intraday data
        data = getIntradayData(symbolName, timeframe)

        # Evaluate condition
        result = parsedCondition(condition, data).evaluate()
        logger.info(f"[{symbolName}] Condition result: {result}")

        # If result is True and paper trade enabled
        if result and paper_Trade and not data.empty:
            entry_price = data['Close'].iloc[-1]
            currentTime = data.index[-1]
            sl = entry_price * (1 - 2 / 100)
            tp = entry_price * (1 + 5 / 100)

            obj = {
                "symbol": symbolName,
                "action": "BUY",
                "quantity": 1,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "signal_time":currentTime,
                "strategyId": str(strategy.id),
            }

            # Schedule async DB insert on main event loop safely
            future = asyncio.run_coroutine_threadsafe(create_paper_Order(obj), main_loop)
            paper_trade_data = future.result()  # wait until complete
            logger.info(f"Paper trade stored: {paper_trade_data}")

        # Store result in shared dict
        with lock:
            results[symbolName] = result
            logger.info(f"[{symbolName}] Done")

    except Exception as e:
        with lock:
            results[symbolName] = f"Error: {e}"
        logger.error(f"{symbolName} failed: {e}", exc_info=True)

def EvaluteStrategy(strategy, paper_Trade=False):
    threads = []
    results = {}
    lock = threading.Lock()

    # Get the main asyncio event loop from FastAPI or main thread
    main_loop = asyncio.get_event_loop()

    # If strategy is a Beanie document, access orderDetails.symbol as list of objects
    symbols = strategy.orderDetails.symbol

    # Start a thread per symbol
    for sym in symbols:
        symbolName = sym.name
        t = threading.Thread(
            target=worker,
            args=(symbolName, strategy, results, lock, paper_Trade, main_loop)  # pass main_loop
        )
        t.start()
        threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()

    return results

def Backtest_Worker(symbolName, strategy, results, lock):
    try:
        print(f"🔹 {symbolName}: Thread started")

        condition = strategy['condition']
        data = getIntradayData(symbolName, interval="1d", period="5y")

        if data is None or data.empty:
            print(f"⚠️ {symbolName}: No data returned")
            with lock:
                results.append({
                    "symbol": symbolName,
                    "error": "No data returned",
                    "metrices": {},
                    "trades": []
                })
            return

        position = None
        backtestResults = []
        winning_pnl = 0
        winning_trades = 0
        lossing_trade = 0
        lossing_pnl = 0

        start_index = 50  # ensure indicators have enough history

        for idx in range(start_index, len(data)):
            newData = data.iloc[:idx]
            close_price = newData['Close'].iloc[-1]
            currentTime = data.index[idx]

            # safe condition evaluation
            try:
                node = parsedCondition(condition, data.iloc[:idx])
                if node is None:
                    print(f"⚠️ {symbolName}: parsedCondition() returned None")
                    signal = False
                else:
                    signal = node.evaluate()
            except Exception as cond_err:
                print(f"⚠️ {symbolName}: Condition evaluation error -> {cond_err}")
                signal = False

            # ENTRY condition
            if signal and position is None:
                atr = tb.ATR(newData['High'], newData['Low'], newData['Close'], timeperiod=14).iloc[-1]
                entry_price = close_price
                entry_time = currentTime
                sl_price = entry_price - atr * 1.5
                tp_price = entry_price + atr * 3.0

                position = {
                    "type": "Long",
                    "entry_price": entry_price,
                    "entry_time": entry_time,
                    "sl_price": sl_price,
                    "tp_price": tp_price
                }

            # EXIT condition
            elif position is not None:
                last_price = close_price
                if last_price >= position['tp_price']:
                    position["exit_price"] = last_price
                    position["exit_time"] = currentTime
                    position["exit_reason"] = "TP Hit"

                    backtestResults.append(position)
                    winning_pnl += last_price - position["entry_price"]
                    winning_trades += 1
                    position = None

                elif last_price <= position['sl_price']:
                    position["exit_price"] = last_price
                    position["exit_time"] = currentTime
                    position["exit_reason"] = "SL Hit"

                    backtestResults.append(position)
                    lossing_pnl += last_price - position["entry_price"]
                    lossing_trade += 1
                    position = None

        # --- Final Metrics ---
        metrices = {
            "total_trades": len(backtestResults),
            "winning_trades": winning_trades,
            "lossing_trades": lossing_trade,
            "winning_pnl": round(winning_pnl, 2),
            "lossing_pnl": round(lossing_pnl, 2),
            "total_pnl": round(winning_pnl + lossing_pnl, 2),
        }

        if metrices["total_trades"] > 0:
            metrices["win_rate"] = round((winning_trades / metrices["total_trades"]) * 100, 2)
        else:
            metrices["win_rate"] = 0.0

        # thread-safe result append
        with lock:
            results.append({
                "symbol": symbolName,
                "metrices": metrices,
                "trades": backtestResults
            })
            print(f"✅ {symbolName}: Completed with {metrices['total_trades']} trades")

    except Exception as e:
        # store the error safely
        with lock:
            results.append({
                "symbol": symbolName,
                "error": str(e),
                "metrices": {},
                "trades": []
            })
        print(f"❌ {symbolName}: Error -> {e}")

def BacktestStrategy(strategy):
    print("🚀 Backtest started for:", strategy["strategyName"])
    threads = []
    results = []
    lock = threading.Lock()

    symbols = strategy['orderDetails']['symbol']

    for sym in symbols:
        symbolName = sym['name']
        t = threading.Thread(target=Backtest_Worker, args=(symbolName, strategy, results, lock))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("✅ All threads completed!")
    return results

# Example usage:
strategy = {
  "strategyName": "Backtest",
  "category": "High Frequency",
  "description": "test",
  "timeframe": "15m",

  "conditionPreview": "SMA(50) > SMA(200) And MACD-signal(12, 26, 9) < MACD-macd(12, 26, 9)",

  "condition": [
    # ---- Condition 1 ----
    {
      "name": "SMA",
      "type": "indicator",
      "category": "trend",
      "orderType": "value",
      "params": {"period": "50"},
      "sourceAllowed": True
    },
    {
      "name": ">",
      "type": "condition"
    },
    {
      "name": "SMA",
      "type": "indicator",
      "category": "trend",
      "orderType": "value",
      "params": {"period": "200"},
      "sourceAllowed": True
    },

    # ---- Logical operator ----
    {
      "type": "logicalOperator",
      "name": "And"
    },

    # ---- Condition 2 ----
    {
      "name": "MACD-signal",
      "type": "indicator",
      "category": "momentum",
      "orderType": "multi-line",
      "params": {"fast": 12, "slow": 26, "signal": 9},
      "lines": ["macd", "signal", "histogram"],
      "sourceAllowed": True
    },
    {
      "name": "<",
      "type": "condition"
    },
    {
      "name": "MACD-macd",
      "type": "indicator",
      "category": "momentum",
      "orderType": "multi-line",
      "params": {"fast": 12, "slow": 26, "signal": 9},
      "lines": ["macd", "signal", "histogram"],
      "sourceAllowed": True
    }
  ],

  "orderDetails": {
    "action": "BUY",
    "orderType": "Futures",
    "quantity": "750",
    "SL": "2",
    "TP": "5",
    "symbol": [
      {"name": "RELIANCE", "theStrategyMatch": False}
    ]
  }
}


# results = BacktestStrategy(strategy)
# print("Backtest results:", results)
