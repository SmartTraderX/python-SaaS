import logging
from kiteconnect import KiteConnect
import json
import os

logging.basicConfig(level=logging.DEBUG)

api_key = "0cwxwjv4xkjxhale"
api_secret = "mn5oezjdmpv0gbx72f0s6n81ucqa1gqj"

TOKEN_FILE = "access_token.json"


# ---------------------------------------------------------
# SAVE ACCESS TOKEN TO FILE
# ---------------------------------------------------------
def save_access_token(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": token}, f)


# ---------------------------------------------------------
# LOAD ACCESS TOKEN FROM FILE
# ---------------------------------------------------------
def load_access_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return json.load(f).get("access_token")


# ---------------------------------------------------------
# GENERATE NEW ACCESS TOKEN (USER PROVIDES REQUEST TOKEN)
# ---------------------------------------------------------
def generate_access_token(kite):
    print("\n🔗 Open this URL in browser & Login Zerodha:")
    print(kite.login_url())
    print("\nAfter login, copy the **request_token** from redirect URL:")
    request_token = input("Paste request_token here: ").strip()

    data = kite.generate_session(request_token, api_secret)
    access_token = data["access_token"]
    save_access_token(access_token)

    print("\n✅ NEW ACCESS TOKEN GENERATED & SAVED!")
    return access_token


# ---------------------------------------------------------
# MAIN ORDER FUNCTION
# ---------------------------------------------------------
async def place_order_by_kite(symbol: str, qty: int = 1) -> bool:
    try:
        logging.info("Placing Zerodha Delivery Order")

        kite = KiteConnect(api_key=api_key)

        # Try loading saved access token
        access_token = load_access_token()

        if access_token:
            try:
                kite.set_access_token(access_token)
                profile =kite.profile()  # test API call
                print("🔐 Loaded existing access token.")
                print(profile)
            except:
                print("⚠ Existing access token expired. Generating new one...")
                access_token = generate_access_token(kite)
                kite.set_access_token(access_token)
        else:
            print("⚠ No access token found. Generating new token...")
            access_token = generate_access_token(kite)
            kite.set_access_token(access_token)

        # PLACE ORDER
        entry_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol=symbol,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=qty,
            product=kite.PRODUCT_CNC,
            order_type=kite.ORDER_TYPE_MARKET
        )

        print("🍀 Delivery Order Executed:", entry_id)
        return True

    except Exception as e:
        print("❌ ERROR:", str(e))
        return False


# ---------------------------------------------------------
# MAIN CALL
# ---------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    result = asyncio.run(place_order_by_kite("SBIN"))
    print("Result:", result)
