import operator
import sys
import os
import numpy as np
import pandas as pd
import talib as tb
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
# strategy ={
#     "name": "test",
#     "timeframe": "1m",
#     "condition": 
#    [
#     {
#         "type": "indicator",
#         "category": "volume",
#         "name": "SMA-Volume",
#         "orderType": "value",
#         "params": {"period": 20, "field": "volume"},
#         "sourceAllowed": False
#     },
#     {
#         "type": "condition",
#         "name": ">"
#     },
#     {
#         "type": "indicator",
#         "category": "volume",
#         "name": "Volume",
#         "orderType": "value",
#         "params": {"field": None},
#         "sourceAllowed": False
#     },
#     {
#         "type": "logicalOperator",
#         "value": "And"
#     },
#     {
#         "type": "indicator",
#         "category": "momentum",
#         "name": "MACD-macd",
#         "orderType": "multi-line",
#         "lines": ["macd", "signal", "histogram"],
#         "params": {"fast": 12, "slow": 26, "signal": 9, "field": "close"},
#         "sourceAllowed": True
#     },
#     {
#         "type": "condition",
#         "name": ">"
#     },
#     {
#         "type": "indicator",
#         "category": "momentum",
#         "name": "MACD-signal",
#         "orderType": "multi-line",
#         "lines": ["macd", "signal", "histogram"],
#         "params": {"fast": 12, "slow": 26, "signal": 9, "field": "close"},
#         "sourceAllowed": True
#     },
#     {
#         "type": "logicalOperator",
#         "value": "And"
#     },
#     {
#         "type": "indicator",
#         "category": "trend",
#         "name": "SMA",
#         "orderType": "value",
#         "params": {"period": 50, "field": "close"},
#         "sourceAllowed": False
#     },
#     {
#         "type": "condition",
#         "name": ">"
#     },
#     {
#         "type": "indicator",
#         "category": "trend",
#         "name": "SMA",
#         "orderType": "value",
#         "params": {"period": 100, "field": "close"},
#         "sourceAllowed": False
#     }
# ]
# ,
#     "orderDetails": {
#         "symbol": [
#             {"symbolName": "SBIN", "isExecute": False},
#             # {"symbolName": "TATAMOTORS", "isExecute": False}
#         ]
#     }
# }

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
            op = con['value'].upper()
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
                "signal_time":data['timestamp'].iloc[-1],
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
        print(f"{symbolName}: Thread started")  # Debug

        condition = strategy['condition']
        data = getIntradayData(symbolName ,interval="1d" ,period="5y")

        # print(data)

        if data is None or data.empty:
            raise Exception("No Data Returned")

        position = None
        backtestResults = []
        winning_pnl = 0
        winning_trades = 0
        lossing_trade = 0
        lossing_pnl = 0


        # Start after 50 candles for better indicator calculation
        start_index = 50

        for idx in range(start_index, len(data)):
            newData = data.iloc[:idx]  # NumPy array for indicators
            # print("close",newData['Close'])
            # print("volume",newData['Volume'])
            close_price = newData['Close'].iloc[-1]
            currentTime = data.index[idx]

            # print('signal start')

            signal = parsedCondition(condition, data.iloc[:idx]).evaluate()
          


            # Entry condition
            # print('bhaar',signal)
            if signal and position is None:
                # print(signal)
                atr = tb.ATR(newData['High'], newData['Low'], newData['Close'], timeperiod=14).iloc[-1]
# Entry price
                entry_price = close_price
                entry_time = currentTime

                # ATR-based SL and TP
                sl_price = entry_price - atr * 1.5   # 1.5 ATR below entry
                tp_price = entry_price + atr * 3.0   # 3 ATR above entry
                position = {
                    "type": "Long",
                    "entry_price": entry_price,
                    "entry_time": entry_time,
                    "sl_price": sl_price,
                    "tp_price": tp_price
                }
                # print(position)
            # Exit conditions
            elif position is not None:
                last_price = close_price

                if last_price >= position['tp_price']:
                    position["exit_price"] = last_price
                    position["exit_time"] = currentTime
                    position["exit_reason"] = "TP Hit"
                    
                    # print(position)
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

        # Store results safely
        metrices  = {}
        metrices['total_Trades' ] = len(backtestResults)
        metrices['total_pnl'] = winning_pnl + lossing_pnl 
        metrices["winning_pnl"] = winning_pnl
        metrices['lossing_pnl'] = lossing_pnl
        metrices["winning_trades"] = winning_trades
        metrices["lossing_trade"] = lossing_trade

        if metrices['total_Trades'] > 0:
                metrices['win_rate'] = round((metrices['winning_trades'] / metrices["total_Trades"] ) *100 , 2)
        else :
                metrices["win_rate (%)"] = 0.0
        with lock:
            results.append({
                "symbol":symbolName,
                'metrices' : metrices,
                'trades' : backtestResults
            })
            
            # print(f"{symbolName}: Thread finished")

    except Exception as e:
        with lock:
            results[symbolName] = f"Error: {e}"
            print(f"{symbolName}: Error: {e}")


def BacktestStrategy(strategy):
    threads = []
    results = []
    lock = threading.Lock()

    symbols = strategy['orderDetails']['symbol']
    # print("Symbols to process:", [s['symbolName'] for s in symbols])

    # Start a thread per symbol
    for sym in symbols:
        symbolName = sym['name']
        t = threading.Thread(target=Backtest_Worker, args=(symbolName, strategy, results, lock))
        t.start()
        threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()

    return results


# Example usage:
# results = pd.DataFrame( BacktestStrategy(strategy)).to_csv('results.csv')
# print("Backtest results:", results)
