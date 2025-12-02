
import json
import os
import requests
import pyotp
import urllib.parse
import time
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
file_loc = os.path.join(BASE_DIR, "config.json")

# import json
# import os
# import requests
# import pyotp
# import urllib.parse

# file_loc = "config.json"


def generate_totp(secret):
    """Generate TOTP"""
    try:
        totp = pyotp.TOTP(secret)
        return totp.now()       # IMPORTANT FIX
    except:
        print("❌ Invalid TOTP secret")
        return None



def login():
    """Login to Kotak Neo using TOTP + MPIN"""
    if not os.path.exists(file_loc):
        print("❌ config.json not found")
        return None

    with open(file_loc, "r") as f:
        data = json.load(f)

    # ----------- STEP 1 : TOTP LOGIN -----------
    totp_code = input("Enter your totp ")
    print("Generated TOTP:", totp_code)
    if not totp_code:
        print("❌ Cannot generate TOTP")
        return None

    payload = {
        "mobileNumber": data.get("MOBILE"),
        "ucc": data.get("UCC"),
        "totp": totp_code
    }

    headers = {
        "Authorization": data.get("ACCESS_TOKEN"),
        "neo-fin-key": "neotradeapi",
        "Content-Type": "application/json"
    }

    res = requests.post(data.get("URL_Login"), json=payload, headers=headers)
    response = res.json()
    print("Step 1 Response:", response)

    # --- Handle Errors ---
    if "error" in response:
        print("❌ Login Failed:", response["error"])
        return None

    if "data" not in response:
        print("❌ Unexpected response, 'data' missing")
        return None

    VIEW_TOKEN = response["data"]["token"]
    VIEW_SID = response["data"]["sid"]

    # ----------- STEP 2 : VALIDATE MPIN ----------
    payload = {"mpin": data.get("MPIN")}
    headers = {
        "Authorization": data.get("ACCESS_TOKEN"),
        "neo-fin-key": "neotradeapi",
        "sid": VIEW_SID,
        "Auth": VIEW_TOKEN,
        "Content-Type": "application/json"
    }

    res = requests.post(data.get("URL_Validate"), json=payload, headers=headers)
    response2 = res.json()
    print("Step 2 Response:", response2)

    if "error" in response2:
        print("❌ MPIN validation failed:", response2["error"])
        return None

    TRADING_TOKEN = response2["data"]["token"]
    TRADING_SID = response2["data"]["sid"]
    BASE_URL = response2["data"]["baseUrl"]

    # ----------- SAVE NEW TOKENS ----------
    data["TRADING_TOKEN"] = TRADING_TOKEN
    data["TRADING_SID"] = TRADING_SID
    data["BASE_URL"] = BASE_URL
    data["EXPIRY_TIME"] = time.time()+ (12*60*60)

    with open(file_loc, "w") as f:
        json.dump(data, f, indent=4)

    print("🎉 New Tokens Saved!")

    return data


def format_symbol(symbol, product):
    symbol = symbol.strip().upper()

    # Apply -EQ ONLY FOR CNC delivery orders
    if product == "CNC":
        if not symbol.endswith("-EQ"):
            symbol = symbol + "-EQ"

    return symbol
def place_Order(symbol, qty, order_type="B", price_type="MKT", limit_price="0", product="CNC" ):
    try:
        with open(file_loc, "r") as f:
            data = json.load(f)

        BASE_URL = data.get("BASE_URL")
        TOKEN = data.get("TRADING_TOKEN")
        SID = data.get("TRADING_SID")
        EXPIRY_TIME  = data.get("EXPIRY_TIME")
        current_time = time.time()

        if not TOKEN or not SID or not EXPIRY_TIME or current_time > EXPIRY_TIME:
            login_data = login()
            BASE_URL = login_data["BASE_URL"]
            TOKEN = login_data["TRADING_TOKEN"]
            SID = login_data["TRADING_SID"]

        symbol = format_symbol(symbol, product)    

        url = f"{BASE_URL}/quick/order/rule/ms/place"

        jdata = {
            "am": "NO",
            "dq": "0",
            "es": "nse_cm",
            "mp": limit_price,
            "pc": product,
            "pf": "N",
            "pr": "0",
            "pt": price_type,
            "qt": str(qty),
            "rt": "DAY",
            "tp": "0",
            "ts": symbol,
            "tt": order_type
        }

        # 🔥 KOTAK requires jData AS PLAIN STRING
        body = f"jData={json.dumps(jdata)}"

        headers = {
            "Auth": TOKEN,
            "Sid": SID,
            "neo-fin-key": "neotradeapi",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        print("\nFINAL BODY SENT →", body)

        res = requests.post(url, data=body, headers=headers)

        print("\nOrder Response:", res.text)
        return True

    except Exception as e:
        print("Error:", str(e))
        return False

# result =place_Order("RELIANCE" ,10000)

# print("result ",result)

# login()
# # ts = Trading Symbol
# es = Exchange Segment
# tt = Buy / Sell
# qt = Quantity
# pc = Product (MIS/CNC)
# pt = Price Type (MKT/LMT/SL/SL-M)
# mp = Limit Price
# pr = Trigger Price
# rt = DAY / IOC
# dq = Disclosed Qty
# am = After Market
