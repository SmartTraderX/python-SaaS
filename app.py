from flask import Flask, request, redirect, jsonify
from fyers_apiv3 import fyersModel
import json, time, os
import time
from datetime import datetime
# from kiteConnect import (download_historical_windowed)
app = Flask(__name__)

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

# 🔹 STEP 2: Redirect URL (Zerodha yahan aayega)
@app.route("/zerodha/callback")
def fyers_callback():

    auth_code = request.args.get("auth_code")
    state = request.args.get("state")

    if not auth_code:
        return "❌ auth_code missing", 400

    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        response_type=RESPONSE_TYPE,
        state=STATE,
        secret_key=SECRET_KEY,
        grant_type=GRANT_TYPE
    )

    session.set_token(auth_code)
    response = session.generate_token()

    if "access_token" not in response:
        raise Exception(f"❌ Token error: {response}")

    token = response["access_token"]  

    with open("fyers_access_token.json", "w") as f:
        json.dump(
            {
                "access_token": token,
                "created_at": time.time()
            },
            f,
            indent=4
        )  

    return "✅ FYERS auth_code received & stored."
#
@app.route("/")
def profile():
    return '<h2>Hy Sir </h2>'


if __name__ == "__main__":
    app.run(debug=True)