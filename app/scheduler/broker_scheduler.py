import pyotp
from SmartApi import SmartConnect
from logzero import logger
from datetime import datetime, timedelta
from app.models.user_model import UserModel  # assuming you put your UserModel in models/user.py
from app.models.paper_trade_model import Paper_Trade # assuming you put your UserModel in models/user.py
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import asyncio
import json

CORRELATION_ID = "sl_tp_check"
MODE = 1

import logging

logger = logging(__name__)
# -------------------------------
# Async SmartAPI Login Function
# -------------------------------
async def login_smartapi():
    api_key = '7FutccrO'
    clientCode = 'A556000'
    pwd = '2911'
    secret_key = "9495dd53-06e5-40cc-978c-bbfb4e895901"
    totp_secret = "2JREMUQNBZJZ62HC5ZWULWS4HE"

    # 🔹 Find existing user
    user = await UserModel.find_one({"userId": clientCode, "isDeleted": False})

    # If user not found — create new SmartAPI session
    if not user:
        logger.info("User not found in DB — logging in to SmartAPI...")

        smartApi = SmartConnect(api_key)
        try:
            totp = pyotp.TOTP(totp_secret).now()
        except Exception:
            logger.error("Invalid TOTP secret.")
            raise

        data = smartApi.generateSession(clientCode, pwd, totp)

        if not data.get("status"):
            logger.error(f"Login failed: {data}")
            raise Exception("SmartAPI login failed")

        authToken = data["data"]["jwtToken"]
        refreshToken = data["data"]["refreshToken"]
        feedToken = smartApi.getfeedToken()
        profile = smartApi.getProfile(refreshToken)

        new_user = UserModel(
            clientCode=clientCode,
            pwd=pwd,
            apiKey=api_key,
            secretKey=secret_key,
            authToken=authToken,
            refreshToken=refreshToken,
            feedToken=feedToken,
            tokenExpiry = datetime.now(),
            createdAt=datetime.now(),
            isDeleted=False,
        )
        await new_user.insert()
        logger.info(" New user saved to DB.")

        return {
            "smartApi": smartApi,
            "authToken": authToken,
            "refreshToken": refreshToken,
            "feedToken": feedToken,
            "profile": profile.get("data", {}),
            "from_db": False
        }

    #  If user already exists — reuse tokens
    else:
        logger.info("User found in DB — checking token validity...")
        smartApi = SmartConnect(user.apiKey or api_key)

        try:
            profile = smartApi.getProfile(user.refreshToken)
            if profile.get("status"):
                logger.info(" Existing SmartAPI tokens are valid.")
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
            data = smartApi.generateSession(user.clientCode, user.pwd, totp)

            if not data.get("status"):
                raise Exception("SmartAPI re-login failed")

            authToken = data["data"]["jwtToken"]
            refreshToken = data["data"]["refreshToken"]
            feedToken = smartApi.getfeedToken()

            # Update tokens in DB
            user.authToken = authToken
            user.refreshToken = refreshToken
            user.feedToken = feedToken
            user.expiryTime = datetime.now()
            await user.save()

            logger.info("Tokens refreshed and saved to DB.")

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

async def is_token_expire(user):
    try:
        expirytime = user.get("tokenExpiry")
        if not expirytime:
            return True
        
        if datetime.utcnow() > expirytime:
            return True
        return False
    except Exception:
        return True


async def calculate_sl_tp(user_id):
    try:
        all_paper_trades_task  = Paper_Trade.get({"status":"open"}).to_list()
        user_task   = UserModel.find_One({"_id" : user_id})

        all_paper_trades , user = await asyncio.gather(all_paper_trades_task ,user_task )

        if not all_paper_trades or not user:
            logger.info('No open Paper trades or user')
            return 
        AUTH_TOKEN = user.get("authToken")
        API_KEY = user.get("apiKey")
        CLIENT_CODE = user.get("clientCode")
        FEED_TOKEN = user.get("feedToken")

        if await is_token_expire(user):
            logging.info('token expired , re-logging in SmartApi...')
            login_result = await login_smartapi()

            if not login_result:
                logger.error("failed to refresh token")
                return
            AUTH_TOKEN = login_result["authToken"]
            FEED_TOKEN = login_result["feedToken"]


        symbol_codes = list({trade["symbolCode"] for trade in all_paper_trades})

        if not symbol_codes:
            logger.info('No symbols found in open trades')
            return 
        
        logger.info(f'subscbribing to {len(symbol_codes)} symbols:{symbol_codes}')

           # convert into SmartAPI token list format
        token_list = [{"exchangeType":1 , "tokens":symbol_codes }]
        CORRELATION_ID = f"sl_tp_{user_id}"
        MODE = 1 

        # websocket setup 
        sws = SmartWebSocketV2(AUTH_TOKEN , API_KEY , CLIENT_CODE,FEED_TOKEN)

        async def handle_tick(message):
            try:
                data = json.loads(message)
                for tick in data.get("data",[]):
                    token = str(tick.get("token"))
                    ltp = float(tick.get("ltp",0))

                    # check for SL/TP trigger

                    for trade in all_paper_trades:
                        if str(trade["symbolCode"]) != token:
                            continue
                        side = trade['side']
                        sl = float(trade["stopLoss"])
                        tp = float(trade["takeProfit"])

                        if side == "Buy":
                            if ltp <= sl:
                                await trgigger_order(trade, "StopLoss",ltp)

                            elif ltp >= tp:
                                await trgigger_order(trade , "Target Hit",ltp)
                                
                        elif side == "Sell":
                            if ltp <= sl:
                                await trgigger_order(trade, "StopLoss",ltp)

                            elif ltp >= tp:
                                await trgigger_order(trade , "Target Hit",ltp)       
            except Exception as e:
                raise Exception("Error")
            
        def on_data(wsapp, message):
            asyncio.create_task(handle_tick(message))

        def on_open(wsapp):
            logger.info(" WebSocket connected.")
            sws.subscribe(CORRELATION_ID, MODE, token_list)

        def on_error(wsapp, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(wsapp):
            logger.info("🔒 WebSocket closed.")

        # attach
        sws.on_data = on_data
        sws.on_open = on_open
        sws.on_error = on_error
        sws.on_close = on_close

        # -------------------------
        #Start WebSocket
        # -------------------------
        sws.connect()

    except Exception as e:
        logger.error(f"calculate_sl_tp error: {e}")  


        
async def trgigger_order(trade , reason , price):
    try:
        await Paper_Trade.update_one({"_id": trade["_id"]},{
            "$set":{
                "status":"closed",
                "exit_price" : price,
                    "exitReason": reason,
                    "exitTime": datetime.utcnow().isoformat()

            }
        })
        logger.info(f"{reason} triggered for {trade['symbolCode']} at {price}")
    except Exception as e:
            logger.error(f"Trigger order error: {e}")








 







        

        
            


