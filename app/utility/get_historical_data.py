import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

symbols = ["ADANIENT", "TATASTEEL"]

for sym in symbols:
    ticker = f"{sym}.NS"
    data = yf.download(tickers=ticker, interval="15m", period="60d", progress=False)
    
    # Timezone fix
    if data.index.tz is None:
        data.index = data.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
    else:
        data.index = data.index.tz_convert("Asia/Kolkata")
    
    # Remove running candle
    now = datetime.now().astimezone(pytz.timezone("Asia/Kolkata")).replace(second=0, microsecond=0)
    data = data[data.index < now]
    
    print(f"\n=== {sym} ===")
    print(data)
