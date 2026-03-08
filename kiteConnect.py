from fyers_apiv3 import fyersModel
import webbrowser
import os
import json
from datetime import datetime, timedelta
import pandas as pd


# ================= CONFIG =================
CLIENT_ID = "JDW5YNOJ7Q-100"
SECRET_KEY = "KFT2BXKQCZ"
REDIRECT_URI = "https://suturally-interconfessional-sherise.ngrok-free.dev/zerodha/callback"

RESPONSE_TYPE = "code"
GRANT_TYPE = "authorization_code"
STATE = "sample"

SESSION_DIR = "session"
AUTH_CODE_FILE = os.path.join(SESSION_DIR, "fyers_auth_code.json")
ACCESS_TOKEN_FILE = os.path.join(SESSION_DIR, "fyers_access_token.json")

os.makedirs(SESSION_DIR, exist_ok=True)

# ================= AUTH CODE LOGIN =================
def generate_login_url():
    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        response_type=RESPONSE_TYPE,
        state=STATE,
        secret_key=SECRET_KEY,
        grant_type=GRANT_TYPE
    )

    login_url = session.generate_authcode()
    print("\n🔐 Open this URL and login:\n")
    print(login_url)
    webbrowser.open(login_url, new=1)


 
# ================= FYERS INIT =================

def init_fyers():

    with open("fyers_access_token.json", "r") as f:
        data = json.load(f)

    return fyersModel.FyersModel(
        token=data["access_token"],
        client_id=CLIENT_ID,
        is_async=False,
        log_path=""
    )

# ================= MARKET FUNCTIONS =================

def to_epoch(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp())

def get_historical_data(fyers, symbol, resolution, start_date, end_date):
    data = {
        "symbol": symbol,
        "resolution": resolution,
        "date_format": "0",
        "range_from": to_epoch(start_date),
        "range_to": to_epoch(end_date),
        "cont_flag": "1"
    }
    return fyers.history(data)


def get_quotes(fyers, symbols: list):
    return fyers.quotes({"symbols": ",".join(symbols)})


def get_market_depth(fyers, symbol):
    return fyers.depth({"symbol": symbol, "ohlcv_flag": "1"})


def convert_to_df(hist):

    df = pd.DataFrame(
        hist["candles"],
        columns=["timestamp","Open","High","Low","Close","Volume"]
    )

    # convert epoch → datetime UTC
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)

    # convert UTC → Indian Standard Time
    df["datetime"] = df["datetime"].dt.tz_convert("Asia/Kolkata")

    return df
# ================= MAIN =================

def download_fyers_data(
        fyers,
        symbol,
        timeframe="15",
        start_date="2021-01-01",
        end_date="2026-01-01",
        chunk_days=90,
        save_file=True):

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    all_data = []
    current_start = start_date

    while current_start < end_date:

        current_end = current_start + timedelta(days=chunk_days)

        if current_end > end_date:
            current_end = end_date

        try:
            hist = get_historical_data(
                fyers,
                symbol,
                timeframe,
                current_start.strftime("%Y-%m-%d"),
                current_end.strftime("%Y-%m-%d")
            )

            # API response check
            if not hist or 'candles' not in hist or not hist['candles']:
                print(f"⚠ No candles {current_start.date()} → {current_end.date()} | Response: {hist}")
            else:

                df = pd.DataFrame(
                    hist["candles"],
                    columns=["datetime","Open","High","Low","Close","Volume"]
                )

                df["datetime"] = pd.to_datetime(df["datetime"], unit="s")
                df["datetime"] = df["datetime"].dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata")

                if not df.empty:
                    all_data.append(df)

                print(f"✅ Downloaded {current_start.date()} → {current_end.date()}")

        except Exception as e:
            print(f"❌ Error {current_start.date()} → {current_end.date()} : {e}")

        current_start = current_end + timedelta(days=1)

    if not all_data:
        print("⚠ No data fetched")
        return None

    final_df = pd.concat(all_data)

    final_df = final_df.drop_duplicates()
    final_df = final_df.sort_values("datetime")

    if save_file:
        filename = f"{symbol.replace(':','_')}_{timeframe}.parquet"
        final_df.to_parquet(filename)
        print(f"💾 Saved to {filename}")

    return final_df
# if __name__ == "__main__":


    # 🔁 First time login
  
    # if not os.path.exists(AUTH_CODE_FILE):
    #     generate_login_url()
    #     print("\n👉 Login completed → auth_code Flask callback me save hoga")
    #     exit(0)

    # # 🔑 Generate / Refresh access token
    # generate_login_url()
    # auth_code = read_auth_code()
    # access_token = generate_access_token(auth_code)
    # save_access_token(access_token)

    # 🚀 Init FYERS
    # generate_login_url()
    # fyers = init_fyers()


    # hist = get_historical_data(
    #         fyers,
    #         "NSE:SBIN-EQ",
    #         "15",
    #         "2025-09-23",
    #         "2026-01-01"
    #     )

    # df = download_fyers_data(
    #             fyers,
    #             symbol="NSE:SBIN-EQ",
    #             timeframe="15"
    #         )

    # df.to_csv("data.csv", index=False)
    # data = pd.read_parquet("NSE_SBIN-EQ_15.parquet")
    # print(data)


    # 📊 Historical