import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from datetime import datetime
from logzero import logger
from beanie import PydanticObjectId
from bson import ObjectId
import asyncio
import json
import logging
import os
import sys
import threading

# Make app folder visible for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.user_model import UserModel
from models.paper_trade_model import Paper_Trade
from db.init_db import init_db  # Add DB initialization

logging.basicConfig(level=logging.INFO)

# ----------------------------------------------------
# SmartAPI Login + Token Refresh
# ----------------------------------------------------
async def login_smartapi():
    api_key = "7FutccrO"
    clientCode = "A556000"
    pwd = "2911"
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

        profile = smartApi.getProfile(user.refreshToken)
        if profile.get("status"):
            logger.info("Existing tokens valid.")
            return {
                "authToken": user.authToken,
                "refreshToken": user.refreshToken,
                "feedToken": user.feedToken,
            }

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


# ----------------------------------------------------
# SL/TP Calculation + WebSocket Handling
# ----------------------------------------------------

# Keep a global event-loop reference so threads can submit tasks to it
try:
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    MAIN_LOOP = asyncio.get_running_loop()
except RuntimeError:
    MAIN_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(MAIN_LOOP)


async def calculate_sl_tp(user_id):
    try:
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

        if await is_token_expired(user):
            logger.info("Token expired — refreshing...")
            refreshed = await login_smartapi()
            tokens.update(refreshed)

        open_trades = await Paper_Trade.find({"status": "open"}).to_list()
        if not open_trades:
            logger.info("No open trades found.")
            return

        # Prepare tokens for subscription
        token_list = [
            {
                "exchangeType": 1,  # NSE
                "tokens": [str(t.symbolCode) for t in open_trades],
            }
        ]
        correlation_id = f"sl_tp_{user_id}"
        mode = 1  # LTP mode

        sws = SmartWebSocketV2(
            tokens["authToken"],
            tokens["apiKey"],
            tokens["clientCode"],
            tokens["feedToken"],
        )

        def handle_tick(data):
            try:
                # logger.info(f"Raw Tick: {data}")
                ticks = data if isinstance(data, list) else [data]


                logger.info(f"Raw Tick: {ticks}")
                for tick in ticks:
                    token = str(tick.get("token"))
                    ltp = float(tick.get("last_traded_price", 0)) / 100
                    print(f"Token: {token} | LTP: {ltp}")

                    for trade in open_trades:
                        if str(trade.symbolCode) != token and str(trade.status) != "closed":
                            continue
                        
                        ltp = 1525
                        side = trade.action.upper()
                        sl = float(trade.stop_loss)
                        tp = float(trade.take_profit)
                        print(f"symbolCode :{trade.symbolCode} sl: {sl} | tP: {tp}")

                        if side == "BUY":
                            if ltp <= sl:
                                print(f"Stop Loss Hit: {token} | {ltp}")
                                asyncio.run_coroutine_threadsafe(trigger_order(trade, "StopLoss", ltp) , loop)
                            elif ltp >= tp:
                                print(f"Target Hit: {token} | {ltp}")
                                asyncio.run_coroutine_threadsafe(trigger_order(trade, "TargetHit", ltp),loop)
                        elif side == "SELL":
                            if ltp >= sl:
                                print(f"Stop Loss Hit: {token} | {ltp}")
                                asyncio.run(trigger_order(trade, "StopLoss", ltp))
                            elif ltp <= tp:
                                print(f"Target Hit: {token} | {ltp}")
                                asyncio.run(trigger_order(trade, "TargetHit", ltp))

            except Exception as e:
                logger.error(f"Tick error: {e}")

        def on_data(wsapp, message):
            try:
                data = json.loads(message) if isinstance(message, str) else message

                handle_tick(data)
            except Exception as e:
                logger.error(f"on_data error: {e}")

        def on_open(wsapp):
            try:
                logger.info("WebSocket connected — subscribing now.")
                sws.subscribe(correlation_id, mode, token_list)
                logger.info(f"Subscribed to tokens: {[t['tokens'] for t in token_list]}")
            except Exception as e:
                logger.error(f"Subscription error: {e}")

        def on_error(wsapp, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(wsapp, close_status_code, close_msg):
            logger.warning(f"WebSocket closed ({close_status_code}): {close_msg}")

        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_error = on_error
        sws.on_close = on_close

        sws.connect()
        logger.info("WebSocket started in background.")

    except Exception as e:
        logger.error(f"calculate_sl_tp error: {e}", exc_info=True)
        print(f"calculate_sl_tp error: {e}")


# ----------------------------------------------------
# Trigger Trade Close (SL/TP Hit)
# ----------------------------------------------------
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

        print(f"{reason} triggered for {trade.symbolCode} at {price} user:{user}")

    except Exception as e:
        logger.error(f"Trigger order error: {e}")


# ----------------------------------------------------
# Main Entry Point (Standalone)
# ----------------------------------------------------
async def main():
    await init_db()  # ✅ Initialize MongoDB before using models
    await calculate_sl_tp("6905f6e134e7250e9e8b3389")


if __name__ == "__main__":
    asyncio.run(main())

