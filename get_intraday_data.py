import json
import time
from datetime import datetime, timedelta
import upstox_client
import pandas as pd

file_loc = "config.json"


def login_in_upstox():
    your_access_token = input("Enter your Upstox Access Token: ")

    data = {
        "Expiry_Time_UPSTOX": time.time() + (12 * 60 * 60),
        "Access_Token_UPSTOX": your_access_token
    }

    with open(file_loc, "w") as f:
        json.dump(data, f, indent=4)

    print("✔ Upstox token saved successfully")
    return your_access_token


def get_intraday(symbol="NSE_FO|49543", interval="5"):
    try:
        # Load token
        try:
            with open(file_loc, "r") as f:
                data = json.load(f)

            access_token = data["Access_Token_UPSTOX"]
            expiry_time = data["Expiry_Time_UPSTOX"]

        except:
            print("⚠ Token missing → Login required")
            access_token = login_in_upstox()
            expiry_time = time.time() + 12*60*60

        if time.time() > expiry_time:
            print("⚠ Token expired → Login again")
            access_token = login_in_upstox()

        # Configure Upstox
        configuration = upstox_client.Configuration()
        configuration.access_token = access_token
        api_instance = upstox_client.HistoryV3Api(upstox_client.ApiClient(configuration))

        # Dates
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print("Fetching:", symbol, interval, from_date, to_date)

        # Correct API call for your SDK version
        response = api_instance.get_historical_candle_data1(
            symbol,
            "minutes",     # unit required
            interval,      # "1", "5", "15"
            to_date,
            from_date
        )

        candles = response.data.candles
        df = pd.DataFrame(candles, columns=[
            "timestamp", "Open", "High", "Low", "Close", "Volume", "oi"
        ])

        df = df.iloc[::-1].reset_index(drop=True)

        # df.to_json("data.json", indent=4)

        # print(df.to_string())
        return df

    except Exception as e:
        print(f"🔥 Error: {str(e)}")

