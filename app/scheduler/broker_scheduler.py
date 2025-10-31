import pyotp
from SmartApi import SmartConnect
from logzero import logger
from datetime import datetime, timedelta
from app.models.user_model import UserModel  # assuming you put your UserModel in models/user.py
from app.models.paper_trade_model import Paper_Trade  # assuming you put your UserModel in models/user.py
import logging

logger = logging(__name__)
# -------------------------------
# Async SmartAPI Login Function
# -------------------------------
async def login_smartapi():
    api_key = '7FutccrO'
    userId = 'A556000'
    pwd = '2911'
    secret_key = "9495dd53-06e5-40cc-978c-bbfb4e895901"
    totp_secret = "2JREMUQNBZJZ62HC5ZWULWS4HE"

    # 🔹 Find existing user
    user = await UserModel.find_one({"userId": userId, "isDeleted": False})

    # If user not found — create new SmartAPI session
    if not user:
        logger.info("User not found in DB — logging in to SmartAPI...")

        smartApi = SmartConnect(api_key)
        try:
            totp = pyotp.TOTP(totp_secret).now()
        except Exception:
            logger.error("Invalid TOTP secret.")
            raise

        data = smartApi.generateSession(userId, pwd, totp)

        if not data.get("status"):
            logger.error(f"Login failed: {data}")
            raise Exception("SmartAPI login failed")

        authToken = data["data"]["jwtToken"]
        refreshToken = data["data"]["refreshToken"]
        feedToken = smartApi.getfeedToken()
        profile = smartApi.getProfile(refreshToken)

        new_user = UserModel(
            userId=userId,
            pwd=pwd,
            apiKey=api_key,
            secretKey=secret_key,
            authToken=authToken,
            refreshToken=refreshToken,
            feedToken=feedToken,
            createdAt=datetime.now(),
            isDeleted=False,
        )
        await new_user.insert()
        logger.info("✅ New user saved to DB.")

        return {
            "smartApi": smartApi,
            "authToken": authToken,
            "refreshToken": refreshToken,
            "feedToken": feedToken,
            "profile": profile.get("data", {}),
            "from_db": False
        }

    # ✅ If user already exists — reuse tokens
    else:
        logger.info("User found in DB — checking token validity...")
        smartApi = SmartConnect(user.apiKey or api_key)

        try:
            profile = smartApi.getProfile(user.refreshToken)
            if profile.get("status"):
                logger.info("✅ Existing SmartAPI tokens are valid.")
                return {
                    "smartApi": smartApi,
                    "authToken": user.authToken,
                    "refreshToken": user.refreshToken,
                    "feedToken": user.feedToken,
                    "profile": profile.get("data", {}),
                    "from_db": True
                }
        except Exception as e:
            logger.warning(f"⚠️ Token expired or invalid: {e}")

        # 🔄 Re-login if token expired
        logger.info("Re-logging in to SmartAPI...")

        try:
            totp = pyotp.TOTP(totp_secret).now()
            data = smartApi.generateSession(user.userId, user.pwd, totp)

            if not data.get("status"):
                raise Exception("SmartAPI re-login failed")

            authToken = data["data"]["jwtToken"]
            refreshToken = data["data"]["refreshToken"]
            feedToken = smartApi.getfeedToken()

            # Update tokens in DB
            user.authToken = authToken
            user.refreshToken = refreshToken
            user.feedToken = feedToken
            user.createdAt = datetime.now()
            await user.save()

            logger.info("✅ Tokens refreshed and saved to DB.")

            profile = smartApi.getProfile(refreshToken)

            return {
                "smartApi": smartApi,
                "authToken": authToken,
                "refreshToken": refreshToken,
                "feedToken": feedToken,
                "profile": profile.get("data", {}),
                "from_db": False
            }

        except Exception as e:
            logger.error(f"❌ Re-login failed: {e}")
            raise


async def caculate_sl_tp():
    try:
        all_paperTrades = await Paper_Trade.get({"status":"open"}).toList()

        if len(all_paperTrades) <= 0:
            logger.info('no paper is found')
            return
        

        
            


