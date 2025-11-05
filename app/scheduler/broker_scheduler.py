import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from datetime import datetime
from logzero import logger
from beanie import PydanticObjectId
from bson import ObjectId
import asyncio
import json
import time
import logging

from app.models.user_model import UserModel
from app.models.paper_trade_model import Paper_Trade

logging.basicConfig(level=logging.INFO)

# -----------------------------
# SmartAPI Login + Token Refresh
# -----------------------------
async def login_smartapi():
    api_key = '7FutccrO'
    clientCode = 'A556000'
    pwd = '2911'
    secret_key = "9495dd53-06e5-40cc-978c-bbfb4e895901"
    totp_secret = "2JREMUQNBZJZ62HC5ZWULWS4HE"

    user = await UserModel.find_one({"clientCode": clientCode, "isDeleted": False})
    smartApi = SmartConnect(api_key)

    try:
        if not user:
            logger.info("No existing user found — creating new session.")
            totp = pyotp.TOTP(totp_secret).now()
            data = smartApi.generateSession(clientCode, pwd, totp)

            if not data.get("status"):
                raise Exception("SmartAPI login failed")

            tokens = {
                "authToken": data["data"]["jwtToken"],
                "refreshToken": data["data"]["refreshToken"],
                "feedToken": smartApi.getfeedToken(),
            }

            new_user = UserModel(
                clientCode=clientCode,
                pwd=pwd,
                apiKey=api_key,
                secretKey=secret_key,
                **tokens,
                tokenExpiry=datetime.utcnow(),
                createdAt=datetime.utcnow(),
                isDeleted=False,
            )
            await new_user.insert()
            logger.info("New SmartAPI user created.")
            return tokens

        # Try existing tokens
        profile = smartApi.getProfile(user.refreshToken)
        if profile.get("status"):
            logger.info("Existing tokens valid.")
            return {
                "authToken": user.authToken,
                "refreshToken": user.refreshToken,
                "feedToken": user.feedToken,
            }

        # Re-login if expired
        logger.info("Token expired — refreshing session.")
        totp = pyotp.TOTP(totp_secret).now()
        data = smartApi.generateSession(clientCode, pwd, totp)

        if not data.get("status"):
            raise Exception("SmartAPI re-login failed")

        user.authToken = data["data"]["jwtToken"]
        user.refreshToken = data["data"]["refreshToken"]
        user.feedToken = smartApi.getfeedToken()
        user.tokenExpiry = datetime.utcnow()
        await user.save()

        return {
            "authToken": user.authToken,
            "refreshToken": user.refreshToken,
            "feedToken": user.feedToken,
        }

    except Exception as e:
        logger.error(f"SmartAPI login failed: {e}")
        raise


async def is_token_expired(user):
    expiry = user.tokenExpiry or datetime.utcnow()
    return (datetime.utcnow() - expiry).total_seconds() > 3600


# -----------------------------
# SL/TP Calculation Background Task

# Store main loop reference globally
MAIN_LOOP = asyncio.get_event_loop()

async def calculate_sl_tp(user_id):
    try:
        # Fetch user
        user = await UserModel.find_one({"_id": PydanticObjectId(user_id)})
        if not user:
            logger.warning("User not found.")
            return

        tokens = {
            "authToken": user.authToken,
            "feedToken": user.feedToken,
            "apiKey": user.apiKey,
            "clientCode": user.clientCode,
        }

        # Refresh token if expired
        if await is_token_expired(user):
            logger.info("Token expired — refreshing...")
            refreshed = await login_smartapi()
            tokens.update(refreshed)

        # Get open trades
        open_trades = await Paper_Trade.find({"status": "open"}).to_list()
        if not open_trades:
            logger.info("No open trades found.")
            return

        symbols = list({t.symbolCode for t in open_trades})
        token_list = [{"exchangeType": 1, "tokens": symbols}]
        correlation_id = f"sl_tp_{user_id}"
        mode = 1

        # Initialize SmartWebSocket
        sws = SmartWebSocketV2(
            tokens["authToken"],
            tokens["apiKey"],
            tokens["clientCode"],
            tokens["feedToken"],
        )

        # -----------------------------
        # Async tick handler
        # -----------------------------
        async def handle_tick(message):
            try:
                data = json.loads(message)
                print("data",data)
                for tick in data.get("data", []):
                    token = str(tick.get("token"))
                    ltp = float(tick.get("ltp", 0)) / 100

                    for trade in open_trades:
                        if str(trade.symbolCode) != token:
                            continue

                        side = trade.action
                        sl = float(trade.stop_loss)
                        tp = float(trade.take_profit)

                        if side.upper() == "BUY":
                            if ltp <= sl:
                                await trigger_order(trade, "StopLoss", ltp)
                            elif ltp >= tp:
                                await trigger_order(trade, "TargetHit", ltp)
                        elif side.upper() == "SELL":
                            if ltp >= sl:
                                await trigger_order(trade, "StopLoss", ltp)
                            elif ltp <= tp:
                                await trigger_order(trade, "TargetHit", ltp)
            except Exception as e:
                logger.error(f"Tick error: {e}")

        # -----------------------------
        # WebSocket event handlers
        # -----------------------------
        def on_data(wsapp, message):
            try:
                asyncio.run_coroutine_threadsafe(handle_tick(message), MAIN_LOOP)
            except RuntimeError as e:
                logger.error(f"on_data loop error: {e}")

        def on_open(wsapp):
            logger.info("WebSocket connected.")
            sws.subscribe(correlation_id, mode, token_list)

        def on_error(wsapp, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(wsapp, close_status_code, close_msg):
            logger.warning(
                f"WebSocket closed ({close_status_code}): {close_msg}. Reconnecting in 5 seconds..."
            )

            async def reconnect():
                await asyncio.sleep(5)
                logger.info("Reconnecting WebSocket...")
                MAIN_LOOP.run_in_executor(None, sws.connect)

            try:
                MAIN_LOOP.create_task(reconnect())
            except RuntimeError:
                logger.error("Reconnect failed — no running loop")

        # Attach handlers
        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_error = on_error
        sws.on_close = on_close

        # Start WebSocket in background thread
        MAIN_LOOP.run_in_executor(None, sws.connect)
        logger.info("WebSocket started in background successfully.")

    except Exception as e:
        logger.error(f"calculate_sl_tp error: {e}", exc_info=True)


# -----------------------------
# Trigger Trade Close (SL/TP Hit)
# -----------------------------
async def trigger_order(trade, reason, price):
    try:
        entry_price = float(trade.entry_price)
        pnl = price - entry_price if trade.action.upper() == "BUY" else entry_price - price

        await Paper_Trade.find_one({"_id": trade.id}).update(
            {
                "$set": {
                    "status": "closed",
                    "exit_price": price,
                    "exitReason": reason,
                    "exitTime": datetime.utcnow(),
                    "pnl": pnl,
                }
            }
        )

        user = await UserModel.find_one({"_id": ObjectId("6905f6e134e7250e9e8b3389")})
        if user:
            await user.update({"$inc": {"margin": pnl}})
        logger.info(f"{reason} triggered for {trade.symbolCode} at {price}")

    except Exception as e:
        logger.error(f"Trigger order error: {e}")
