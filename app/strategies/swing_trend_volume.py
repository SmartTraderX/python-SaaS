
from app.services.strategy_evalutation_services import  (swingHigh , swingLow , volumecheck)
from app.utility.get_historical_data import (getIntradayData)
import talib as tb
from app.services.broker_service import (place_Order)


async def swingLow_volume_trend_rsi_buy(symbol: str = "SBIN", timeframe: str = "15m"):
    try:
        data = getIntradayData(symbol, timeframe)

        if data is None or data.empty:
            print(f"{symbol}: Data is Empty")
            return
        
        # ---- Volume Check ---- 
        ok_volume = volumecheck(data)

        # ---- Extract Latest Candle ----
        open_ = data['Open'].iloc[-1]
        close_ = data['Close'].iloc[-1]
        high = data['High'].iloc[-1]
        low = data['Low'].iloc[-1]

        prev_open = data['Open'].iloc[-2]
        prev_close = data['Close'].iloc[-2]
        prev_high = data['High'].iloc[-2]
        prev_low = data['Low'].iloc[-2]

        # ---- Candle Strength ----
        body = abs(close_ - open_)
        full = high - low
        is_strong_body = full > 0 and body >= 0.5 * full

        # ---- Indicators ----
        rsi = float(tb.RSI(data['Close'], timeperiod=14).iloc[-1])
        sma20 = float(tb.SMA(data['Close'], timeperiod=20).iloc[-1])
        sma50 = float(tb.SMA(data['Close'], timeperiod=50).iloc[-1])
        sma200 = float(tb.SMA(data['Close'], timeperiod=200).iloc[-1])

        # ---- Proper Breakout Logic ----
        is_breakout = high > prev_high and prev_high > data['High'].iloc[-3]

        # ---- Swing Low ----
        swing_low_value = swingLow(data)

        signal = False

        # ---------- STRATEGY 1: SWING + TREND + VOLUME ----------
        if (
            swing_low_value is not None
            and is_strong_body
            and sma20 > sma50 > sma200     # uptrend confirmation
            and rsi > 50
            and ok_volume
        ):
            signal = True

        # ------------- STRATEGY 2: BREAKOUT + TREND + VOLUME -------------
        elif (
            ok_volume
            and sma50 > sma200
            and is_strong_body
            and is_breakout
        ):
            signal = True

        # -------------------- PLACE ORDER --------------------
        if signal:
            order = place_Order(symbol, qty=2, order_type="B")
            
            if order:
                print(f"Order Placed Successfully for {symbol}")
                return
            
            print("Error: Order not placed")

    except Exception as e:
        print(f"Error: {str(e)}")
   
async def swingHigh_volume_trend_rsi_buy(symbol:str="SBIN" , timframe :str ="15m"):
    try:
        data = getIntradayData(symbol , timframe)
        if data is None:
            print('Data is Empty for this symbol')
            return
        # volume check 
        ok_volume = volumecheck(data)
        # current
        open = data['Open'].iloc[-1]
        close = data['Close'].iloc[-1]
        high = data['High'].iloc[-1]
        low = data['Low'].iloc[-1]

        body = abs(close-open)
        full = high -low

        is_strong_body = body >= ( 0.5 * full)

        swing_low_value = swingHigh(data)
        val = float(tb.RSI(data['Close'], timeperiod=14).iloc[-1])
        sma_20 = float(tb.SMA(data['Close'], timeperiod=20).iloc[-1])
        sma_50 = float(tb.SMA(data['Close'], timeperiod=50).iloc[-1])
        sma_200 = float(tb.SMA(data['Close'], timeperiod=200).iloc[-1])

        if( 
            swing_low_value and swing_low_value != 0 
            and is_strong_body 
            and sma_20 < sma_50
            and sma_50 < sma_200
            and val < 50
            and ok_volume
        ):
            order =  place_Order(symbol,qty=2 , order_type="S")
            if order :
                print("Order Place SuccssFully for This Symbol{symbol}")
                return 
            else:
                print("Error")  
        else : print(f"condtion for symbol {symbol}  for this timframe{timframe}")   
    except Exception as e:
        print(f"error {str(e)}")
        

 



        
      


