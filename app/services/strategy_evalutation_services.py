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
# from app.services.paper_trade_service import (create_paper_Order)
# from app.services.strategy_service import (mark_symbol_match)
# from app.models.strategy_model import Strategy
# from app.logger import logger

def supertrend(data, period=10, multiplier=3):
    """
    Calculate SuperTrend Indicator
    data: DataFrame with columns ['low', 'Low', 'Close']
    period: ATR period (default 10)
    multiplier: multiplier for ATR (default 3)
    """

    low = data['low']
    low = data['Low']
    close = data['Close']

    # Step 1: Calculate ATR
    atr = tb.ATR(low.values, low.values, close.values, timeperiod=period)

    # Step 2: Calculate basic bands
    hl2 = (low + low) / 2
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    # Step 3: Initialize SuperTrend array
    supertrend = np.zeros(len(data))
    final_upperband = np.zeros(len(data))
    final_lowerband = np.zeros(len(data))

    for i in range(1, len(data)):
        # upper band
        if (upperband[i] < final_upperband[i - 1]) or (close[i - 1] > final_upperband[i - 1]):
            final_upperband[i] = upperband[i]
        else:
            final_upperband[i] = final_upperband[i - 1]

        # lower band
        if (lowerband[i] > final_lowerband[i - 1]) or (close[i - 1] < final_lowerband[i - 1]):
            final_lowerband[i] = lowerband[i]
        else:
            final_lowerband[i] = final_lowerband[i - 1]

        # Supertrend direction
        if supertrend[i - 1] == final_upperband[i - 1] and close[i] <= final_upperband[i]:
            supertrend[i] = final_upperband[i]
        elif supertrend[i - 1] == final_upperband[i - 1] and close[i] > final_upperband[i]:
            supertrend[i] = final_lowerband[i]
        elif supertrend[i - 1] == final_lowerband[i - 1] and close[i] >= final_lowerband[i]:
            supertrend[i] = final_lowerband[i]
        elif supertrend[i - 1] == final_lowerband[i - 1] and close[i] < final_lowerband[i]:
            supertrend[i] = final_upperband[i]
        else:
            supertrend[i] = hl2[i]

    return pd.DataFrame({
        'SuperTrend': supertrend,
        'FinalUpperBand': final_upperband,
        'FinalLowerBand': final_lowerband,
        'ATR': atr
    })

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

def swingHigh(data, isBoolean: bool = False, window: int = 2):
    if len(data) < window * 2 + 1:
        print("Data is too short")
        return None

    # last (2*window+1) candles
    recent = data.iloc[-(window * 2 + 1):]
    mid_idx = window

    middle_high = recent["High"].iloc[mid_idx]
    left_high = recent["High"].iloc[:mid_idx]
    right_high = recent["High"].iloc[mid_idx + 1:]

    # swing high = middle candle higher than both sides
    if middle_high > max(left_high) and middle_high > max(right_high):
        swing_high = middle_high
        return True if isBoolean else swing_high

    return False if isBoolean else 0


def swingLow(data, isBoolean: bool = False, window: int = 2):
    if len(data) < window * 2 + 1:
        print("Data is too short")
        return None

    # last (2*window+1) candles
    recent = data.iloc[-(window * 2 + 1):]
    mid_idx = window

    middle_low = recent["Low"].iloc[mid_idx]
    left_low = recent["Low"].iloc[:mid_idx]
    right_low = recent["Low"].iloc[mid_idx + 1:]

    # swing low = middle candle lower than both sides
    if middle_low < min(left_low) and middle_low < min(right_low):
        swing_low = middle_low
        # val = float(tb.RSI(data['Close'], timeperiod=14).iloc[-1])
        # if val < 40 :
        return True if isBoolean else swing_low
    
    return False if isBoolean else 0



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

        # handling two case first is close price and 2 is noraml value
        if self.name.lower() == "value":
            val = int(self.params.get("value", 0))

        elif self.name.lower()== "closeprice":
            para = int(self.params.get('value',0))
            val = float(self.data['Close'].iloc[-1])
         
        #  indicator clacutating 
        elif self.name.lower() == "rsi":
            period = int( self.params.get("period", 20) if isinstance(self.params, dict) else 20)
            val = float(tb.RSI(self.data['Close'], timeperiod=period).iloc[-1])
          
        elif self.name.lower() == "volume":
            val = float(self.data['Volume'].iloc[-1])

        elif self.name.lower() in ["sma"]:
            period = int( self.params.get("period", 20) if isinstance(self.params, dict) else 20)
            val = float(tb.SMA(self.data['Close'], timeperiod=period).iloc[-1])    

        elif self.name.lower()  == "swing-high":
            window = int( self.params.get("window", 2) if isinstance(self.params, dict) else 2)
            val = float(swingHigh(self.data))    

        elif self.name.lower()  == "swing-low":
            window = int( self.params.get("window", 2) if isinstance(self.params, dict) else 2)
            val = float(swingLow(self.data))    
  
        elif self.name.lower() in ["sma-volume"]:
            period = int(self.params.get("period", 20) if isinstance(self.params, dict) else 20)
            val = float(tb.SMA(self.data['Volume'], timeperiod=period).iloc[-1]) *1.5
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
        elif self.name.lower() == "stochastic-k":
            k, d = tb.STOCH(
                self.data['Low'].values,
                self.data['Low'].values,
                self.data['Close'].values,
                fastk_period=self.params.get("fastk_period", 14),
                slowk_period=self.params.get("slowk_period", 3),
                slowk_matype=0,
                slowd_period=self.params.get("slowd_period", 3),
                slowd_matype=0
            )
            val = float(k[-1])

        elif self.name.lower() == "stochastic-d":
            k, d = tb.STOCH(
                self.data['Low'].values,
                self.data['Low'].values,
                self.data['Close'].values,
                fastk_period=self.params.get("fastk_period", 14),
                slowk_period=self.params.get("slowk_period", 3),
                slowk_matype=0,
                slowd_period=self.params.get("slowd_period", 3),
                slowd_matype=0
            )
            val = float(d[-1])

        elif self.name.lower() == "bollinger-bands-upper":
            period = int(self.params.get("period", 20))
            deviation = float(self.params.get("deviation", 2))
            upper, middle, lower = tb.BBANDS(
                self.data["Close"].values,
                timeperiod=period,
                nbdevup=deviation,
                nbdevdn=deviation,
                matype=0  # 0 = simple moving average
            )
            val = float(upper[-1])

        elif self.name.lower() == "bollinger-bands-middle":
            period = int(self.params.get("period", 20))
            deviation = float(self.params.get("deviation", 2))
            upper, middle, lower = tb.BBANDS(
                self.data["Close"].values,
                timeperiod=period,
                nbdevup=deviation,
                nbdevdn=deviation,
                matype=0
            )
            val = float(middle[-1])

        elif self.name.lower() == "bollinger-bands-lower":
            period = int(self.params.get("period", 20))
            deviation = float(self.params.get("deviation", 2))
            upper, middle, lower = tb.BBANDS(
                self.data["Close"].values,
                timeperiod=period,
                nbdevup=deviation,
                nbdevdn=deviation,
                matype=0
            )
            val = float(lower[-1])
                # --- ADX (Average Directional Movement Index) ---
                
        elif self.name.lower() == "adx":
            period = int(self.params.get("period", 14))
            val = float(tb.ADX(
                self.data["Low"].values,
                self.data["Low"].values,
                self.data["Close"].values,
                timeperiod=period
            )[-1])

        # --- DMI Plus (DI+) ---
        elif self.name.lower() in ["dmi-plus", "plus-di"]:
            period = int(self.params.get("period", 14))
            val = float(tb.PLUS_DI(
                self.data["Low"].values,
                self.data["Low"].values,
                self.data["Close"].values,
                timeperiod=period
            )[-1])

        # --- DMI Minus (DI-) ---
        elif self.name.lower() in ["dmi-minus", "minus-di"]:
            period = int(self.params.get("period", 14))
            val = float(tb.MINUS_DI(
                self.data["Low"].values,
                self.data["Low"].values,
                self.data["Close"].values,
                timeperiod=period
            )[-1])

        # --- ATR (Average True Range) ---
        elif self.name.lower() == "atr":
            period = int(self.params.get("period", 14))
            val = float(tb.ATR(
                self.data["Low"].values,
                self.data["Low"].values,
                self.data["Close"].values,
                timeperiod=period
            )[-1])
    
    

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
        print('left',left_val)
        print('op',self.op)
        print('right',right_val)
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
            print(f'print-left {self.left} print-e=rigth {self.op} , right{self.right}')
           
            result= self.left.evaluate() and self.right.evaluate()
            print( "result",result)
            return result
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

    if not conditions or len(conditions) == 0:
        return None
    

    if len(conditions) == 3 and conditions[1]['type'] == "condition":
       return convertInNodes(conditions ,data)

    logic_ops =[]
    parts = []
    start = 0


    for idx , con in enumerate(conditions):
        if con['type'] == "logicalOperator":

            logic_ops.append(con['name'].upper())
            parts.append(conditions[start:idx])
            start = idx + 1
    parts.append(conditions[start:])        

    nodes =[]

    for part in parts:
        node = None
        # Handle sub-parts of variable lengths
        if len(part) >= 3:
            # Use last 3 elements if too long
            if part[-2]['type'] == 'condition':
                node = convertInNodes(part[-3:], data)
            else:
                node = parsedCondition(part, data)
        elif len(part) == 3:
            node = convertInNodes(part, data)
        else:
            continue  # skip incomplete ones
        if node:
            nodes.append(node)

        # 🪢 Chain logical operators left-to-right
    if not nodes:
        return None

    result = nodes[0]
    for idx, op in enumerate(logic_ops):
        if idx + 1 < len(nodes):
            result = LogicalNode(result, op, nodes[idx + 1])

    return result        

def worker(symbolName, symbolid, strategy, results, lock, paper_Trade, main_loop):
    """
    Evaluates strategy conditions + swing structure for each symbol,
    and creates paper orders accordingly.
    """
    try:
        timeframe = strategy.timeframe
        condition = strategy.condition

        # 🔹 Get intraday data
        data = getIntradayData(symbolName, timeframe)
        if data is None or data.empty:
            logger.warning(f"[{symbolName}] No data fetched")
            with lock:
                results[symbolName] = {"error": "No data"}
            return

        # 🔍 Always check swing structure
        isSwingHigh = swingHigh(data, True)
        isSwingLow = swingLow(data, True)

        # 🔸 Evaluate strategy condition
        result = parsedCondition(condition, data).evaluate()
        logger.info(f"[{symbolName}] Condition={result}, SwingHigh={isSwingHigh}, SwingLow={isSwingLow}")

        # 📊 Store intermediate results for analysis
        with lock:
            results[symbolName] = {
                "condition": result,
                "swingHigh": isSwingHigh,
                "swingLow": isSwingLow,
            }

        # 🧾 Helper for creating async paper trades
        def create_paper_trade(action):
            entry_price = data["Close"].iloc[-1]
            currentTime = data.index[-1]
            sl = entry_price * (1 - 0.02) if action == "BUY" else entry_price * (1 + 0.02)
            tp = entry_price * (1 + 0.05) if action == "BUY" else entry_price * (1 - 0.05)

            obj = {
                "symbol": symbolName,
                "action": action,
                "quantity": 500,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "signal_time": currentTime,
                "strategyId": str(strategy.id),
            }

            future = asyncio.run_coroutine_threadsafe(create_paper_Order(obj), main_loop)
            paper_trade_data = future.result()
            logger.info(f"[{symbolName}] Paper trade stored: {paper_trade_data}")
            asyncio.run_coroutine_threadsafe(mark_symbol_match(strategy.id, symbolid), main_loop)

        # 🟢 Swing-based signals (independent from condition)
        if paper_Trade and not data.empty:
            if isSwingHigh:
                create_paper_trade("SELL")
            elif isSwingLow:
                create_paper_trade("BUY")

        # 🔵 Condition-based signal (main strategy)
        if result and paper_Trade and not data.empty:
            create_paper_trade("BUY")

        logger.info(f"[{symbolName}] Worker completed successfully.")

    except Exception as e:
        with lock:
            results[symbolName] = {"error": str(e)}
        logger.exception(f"Error while evaluating {symbolName} in strategy {strategy.strategyName}: {e}")

def EvaluteStrategy(strategy, paper_Trade=False):
    threads = []
    results = {}
    lock = threading.Lock()

    # Get the main asyncio event loop from FastAPI or main thread
    main_loop = asyncio.get_event_loop()

    # If strategy is a Beanie document, access orderDetails.symbol as list of objects
    symbols = strategy.orderDetails.symbol

    symbols_to_process = [sym for sym in symbols if not getattr(sym, "theStrategyMatch", False)]

    if not symbols_to_process :
        logger.info(f"No new symbols left to process for strategy {strategy.strategyName}")
        return results

    # Start a thread per symbol
    for sym in symbols_to_process:
        symbolName = sym.name
        symbolid =sym.id
        t = threading.Thread(
            target=worker,
            args=(symbolName,symbolid, strategy, results, lock, paper_Trade, main_loop)  # pass main_loop
        )
        t.start()
        threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()

    return results

def worker_test(symbolName, strategy, results, lock, paper_Trade, main_loop):
    """
    Worker function for evaluating a strategy and optionally creating a paper trade.
    main_loop: the asyncio event loop from the main thread
    """
    # try:
    #     # Extract strategy info
    #     timeframe = strategy["timeframe"]
    #     condition = strategy["condition"]

    #     # Get intraday data
    #     data = getIntradayData(symbolName, timeframe)

    #     # Evaluate condition
    #     result = parsedCondition(condition, data).evaluate()
    #     logger.info(f"[{symbolName}] Condition result: {result}")

    #     # If result is True and paper trade enabled
    #     if result and paper_Trade and not data.empty:
    #         entry_price = data['Close'].iloc[-1]
    #         currentTime = data.index[-1]
    #         sl = entry_price * (1 - 2 / 100)
    #         tp = entry_price * (1 + 5 / 100)

    #         obj = {
    #             "symbol": symbolName,
    #             "action": "BUY",
    #             "quantity": 1,
    #             "entry_price": entry_price,
    #             "stop_loss": sl,
    #             "take_profit": tp,
    #             "signal_time":currentTime,
    #             "strategyId": str(strategy.id),
    #         }

    #         # Schedule async DB insert on main event loop safely
    #         future = asyncio.run_coroutine_threadsafe(create_paper_Order(obj), main_loop)
    #         paper_trade_data = future.result()  # wait until complete
    #         logger.info(f"Paper trade stored: {paper_trade_data}")

    #     # Store result in shared dict
    #     with lock:
    #         results[symbolName] = result
    #         logger.info(f"[{symbolName}] Done")

    # except Exception as e:
    #     with lock:
    #         results[symbolName] = f"Error: {e}"
    #     logger.exception(f"Error while evaluating {symbolName} in strategy {strategy.strategyName}: {e}")
    """
    Evaluates strategy conditions + swing structure for each symbol,
    and creates paper orders accordingly.
    """
    try:
        timeframe = strategy["timeframe"]
        condition = strategy["condition"]

        # 🔹 Get intraday data
        data = getIntradayData(symbolName, timeframe)
        if data is None or data.empty:
            logger.warning(f"[{symbolName}] No data fetched")
            with lock:
                results[symbolName] = {"error": "No data"}
            return

        # 🔍 Always check swing structure
        isSwingHigh = swingHigh(data, True)
        isSwingLow = swingLow(data, True)

        # 🔸 Evaluate strategy condition
        result = parsedCondition(condition, data).evaluate()
        logger.info(f"[{symbolName}] Condition={result}, SwingHigh={isSwingHigh}, SwingLow={isSwingLow}")

        # 📊 Store intermediate results for analysis
        with lock:
            results[symbolName] = {
                "condition": result,
                "swingHigh": isSwingHigh,
                "swingLow": isSwingLow,
            }

        # 🧾 Helper for creating async paper trades
        def create_paper_trade(action):
            entry_price = data["Close"].iloc[-1]
            currentTime = data.index[-1]
            sl = entry_price * (1 - 0.02) if action == "BUY" else entry_price * (1 + 0.02)
            tp = entry_price * (1 + 0.05) if action == "BUY" else entry_price * (1 - 0.05)

            obj = {
                "symbol": symbolName,
                "action": action,
                "quantity": 500,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "signal_time": currentTime,
                "strategyId": str(strategy.id),
            }

            future = asyncio.run_coroutine_threadsafe(create_paper_Order(obj), main_loop)
            paper_trade_data = future.result()
            logger.info(f"[{symbolName}] Paper trade stored: {paper_trade_data}")
            asyncio.run_coroutine_threadsafe(mark_symbol_match(strategy.id, symbolid), main_loop)

        # 🟢 Swing-based signals (independent from condition)
        if paper_Trade and not data.empty:
            if isSwingHigh:
                create_paper_trade("SELL")
            elif isSwingLow:
                create_paper_trade("BUY")

        # 🔵 Condition-based signal (main strategy)
        if result and paper_Trade and not data.empty:
            create_paper_trade("BUY")

        logger.info(f"[{symbolName}] Worker completed successfully.")

    except Exception as e:
        with lock:
            results[symbolName] = {"error": str(e)}
        logger.exception(f"Error while evaluating {symbolName} in strategy {strategy.strategyName}: {e}")

def EvaluteStrategy_Testing(strategy, paper_Trade=False):
    threads = []
    results = {}
    lock = threading.Lock()

    # Get the main asyncio event loop from FastAPI or main thread
    main_loop = asyncio.get_event_loop()

    # If strategy is a Beanie document, access orderDetails.symbol as list of objects
    symbols = strategy["orderDetails"]["symbol"]

    # Start a thread per symbol
    for sym in symbols:
        symbolName = sym["name"]
        t = threading.Thread(
            target=worker_test,
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

        condition = strategy["condition"]
        timeframe = strategy["timeframe"]
        data = getIntradayData(symbolName , timeframe)
        print("data", data)

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

        # print('data ', data)

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

            # print('signal ', signal)
            
            if signal and position is None:
                atr = tb.ATR(newData['low'], newData['Low'], newData['Close'], timeperiod=14).iloc[-1]
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
                low = newData['Low'].iloc[-1]
                if low >= position['tp_price']:
                    position["exit_price"] = last_price
                    position["exit_time"] = currentTime
                    position["exit_reason"] = "TP Hit"

                    backtestResults.append(position)
                    winning_pnl += last_price - position["entry_price"]
                    winning_trades += 1
                    position = None

                elif low <= position['sl_price']:
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
            print(f"{symbolName}: Completed with {metrices['total_trades']} trades")

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
    print(" Backtest started for:", strategy["strategyName"])
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

    print("All threads completed!")
    return results
def BacktestStrategy_Testing(strategy):
    print(" Backtest started for:", strategy["strategyName"])
    threads = []
    results = []
    lock = threading.Lock()

    symbols = strategy['orderDetails']['symbol']

    for sym in symbols:
        symbolName = sym['name']
        t = threading.Thread(target=Backtest_Worker_Testing, args=(symbolName, strategy, results, lock))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("All threads completed!")
    return results
# Example usage:

def Backtest_Worker_Testing(symbolName, strategy, results, lock):
    try:
        print(f"🔹 {symbolName}: Thread started")

        timeframe = strategy['timeframe']
        data = getIntradayData(symbolName, timeframe)

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
        losing_trades = 0
        losing_pnl = 0
        start_index = 50  # enough candles for indicators
        signal_count = []
        count = 0


        for idx in range(start_index, len(data)):
            newData = data.iloc[:idx]
            close_price = newData['Close'].iloc[-1]
            currentTime = data.index[idx]

            # --- Condition Evaluation ---
            signal = False
            try:
                swing_high_value = swingLow(newData)
                # print(swing_high_value)
                val = float(tb.RSI(newData['Close'], timeperiod=14).iloc[-1])
                sma_20 = float(tb.SMA(newData['Close'], timeperiod=20).iloc[-1])
                sma_50 = float(tb.SMA(newData['Close'], timeperiod=50).iloc[-1])
                sma_200 = float(tb.SMA(newData['Close'], timeperiod=200).iloc[-1])
                previous_open = newData['Open'].iloc[-2]
                previous_close = newData['Close'].iloc[-2]
                previous_high = newData['High'].iloc[-2]
                previous_low = newData['Low'].iloc[-2]
                high = newData['High'].iloc[-1]
                low = newData['Low'].iloc[-1]
                open = newData['Open'].iloc[-1]
                close = newData['Close'].iloc[-1]

                body = abs(close - open)
                full = high - low

                is_strong_body = body >= (0.5 * full)
                is_breakout = high > previous_high and previous_high > newData['High'].iloc[-3]

                ok_volume = volumecheck(newData)

                if( 
                    # swing_high_value and swing_high_value != 0 
                    # and sma_20 > sma_50
                    sma_50 > sma_200
                    # and val >50
                    and is_breakout
                    and ok_volume
                    and is_strong_body
                ):
                    signal = True
                    # obj = {
                    #     # "data":currentTime,
                    #     "count" : count+1
                    # }
                    count += 1
                    # signal_count.append(obj)
            except Exception as cond_err:
                print(f"⚠️ {symbolName}: Condition evaluation error -> {cond_err}")

            # --- ENTRY ---

            # print(f"sinal{signal} , pos {position}")
 
            
            if signal and position is None:
                atr = float(tb.ATR(newData['High'], newData['Low'], newData['Close'], timeperiod=14).iloc[-1])
                entry_price = close_price
                entry_time = currentTime
                sl_buffer = 1
                sl_price = newData['Low'].iloc[-3] - 5
                # TP = entry price ka 2% upar
                tp_price = entry_price +10# fixed 10 point target

                position = {
                    "type": "BUY",
                    "entry_price": entry_price,
                    "entry_time": str(entry_time),
                    "sl_price": sl_price,
                    "tp_price": tp_price
                }

            # --- EXIT ---
            elif position is not None:
                high = newData['High'].iloc[-1]
                low = newData['Low'].iloc[-1]

                if position["type"] == "BUY":
                    if high >= position['tp_price']:
                        position.update({
                            "exit_price": close_price,
                            "exit_time": str(currentTime),
                            "exit_reason": "TP Hit",
                            "pnl": round(position['tp_price'] - position['entry_price'], 2)
                        })
                        backtestResults.append(position)
                        winning_pnl += position['tp_price'] - position['entry_price']
                        winning_trades += 1
                        position = None

                    elif low <= position['sl_price']:
                        position.update({
                            "exit_price": close_price,
                            "exit_time": str(currentTime),
                            "exit_reason": "SL Hit",
                            "pnl": round(position['sl_price'] - position['entry_price'], 2)
                        })
                        backtestResults.append(position)
                        losing_pnl += position['sl_price'] - position['entry_price']
                        losing_trades += 1
                        position = None

                elif position["type"] == "SELL":

                    if low >= position['tp_price']:
                        position.update({
                            "exit_price": close_price,
                            "exit_time": str(currentTime),
                            "exit_reason": "TP Hit",
                            "pnl": round(position['tp_price'] - position['entry_price'], 2)
                        })
                        backtestResults.append(position)
                        winning_pnl += position['tp_price'] - position['entry_price']
                        winning_trades += 1
                        position = None

                    elif low <= position['sl_price']:
                        position.update({
                            "exit_price": close_price,
                            "exit_time": str(currentTime),
                            "exit_reason": "SL Hit",
                            "pnl": round(position['sl_price'] - position['entry_price'], 2)
                        })
                        backtestResults.append(position)
                        losing_pnl += position['sl_price'] - position['entry_price']
                        losing_trades += 1
                        position = None        

        # --- METRICS ---
        metrices = {
            "total_trades": len(backtestResults),
            "sinal_count" : count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "winning_pnl": round(winning_pnl, 2),
            "losing_pnl": round(losing_pnl, 2),
            "total_pnl": round(winning_pnl + losing_pnl, 2),
            "win_rate": round((winning_trades / len(backtestResults) * 100), 2) if backtestResults else 0.0
        }

        # --- STORE SAFE ---
        with lock:
            results.append({
                "symbol": symbolName,
                "metrices": metrices,
                "trades": backtestResults  # full JSON objects
            })
        print(f"{symbolName}: Completed with {metrices['total_trades']} trades")

    except Exception as e:
        with lock:
            results.append({
                "symbol": symbolName,
                "error": str(e),
                "metrices": {},
                "trades": []
            })
        print(f"❌ {symbolName}: Error -> {e}")


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
    #     "name": "RELIANCE",
    #     "theStrategyMatch": False,
    #     "symbolCode": "3045"
    #   },
    #   {
    #     "id": "690767bade68b5e0109817bf",
    #     "name": "TCS",
    #     "theStrategyMatch": False,
    #     "symbolCode": "3045"
    #   },
    #     {
    #     "id": "690767bade68b5e0109817bf",
    #     "name": "SBIN",
    #     "theStrategyMatch": False,
    #     "symbolCode": "3045"
    #   },
      {
        "id": "690767bade68b5e0109817c0",
        "name": "RELIANCE",
        "theStrategyMatch": False,
        "symbolCode": "2885"
      }
    ]
  },
  "tags": [],
  "totalSubscriber": []
}


def saveInJson(results):
    import json
    with open("result.json","w") as f:
        json.dump({"results":results},f ,indent=4)
        print("save succesfully")


if __name__ == "__main__":

    import asyncio

    
    results = BacktestStrategy_Testing(strategy)
    saveInJson(results)

    # data = getIntradayData("SBIN" , "15m")

    # result = volumecheck(data)

    # print(result)