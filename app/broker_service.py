import httpx
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel
from typing import Optional

# -----------------------
# Helper functions
# -----------------------

def format_to_iso_microseconds(dt):
    return dt.isoformat(timespec="microseconds")

# -----------------------



# -----------------------
# Upstox SDK Class
# -----------------------

class UpstoxSDK:
    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        self.timeout = 15

    # -------------------
    # 1️Get Access Token
    # -------------------
    async def get_access_token(self, credentials: dict):
        try:
            api_key = credentials.get("api_key")
            api_secret = credentials.get("api_secret")
            user_id = credentials.get("userId")
            redirect_url = credentials.get("redirectUrl")
            code = credentials.get("code")

            if not api_key or not user_id:
                raise ValueError("api_key and userId are required")
            if not code:
                raise ValueError("authorization code is required")

            body = {
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_url,
                "grant_type": "authorization_code",
                "code": code,
            }

            data = await self._post(
                "/login/authorization/token",
                body,
                "Error to get token from exchange",
                auth_token=None,
                is_form_urlencoded=True
            )

            if not data or "access_token" not in data:
                raise ValueError("No token received from exchange")

            # Check if broker exists
            existing = await broker_collection.find_one({"clientId": {"$regex": data["user_id"], "$options": "i"}})
            expiry = format_to_iso_microseconds(datetime.utcnow() + timedelta(hours=24))

            if existing:
                await broker_collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "accessToken": data["access_token"],
                        "feedToken": data["extended_token"],
                        "tokenExpiry": expiry
                    }}
                )
                broker_id = existing["_id"]
            else:
                broker_doc = BrokerModel(
                    userId=user_id,
                    name=data.get("user_name", ""),
                    email=data.get("email", ""),
                    clientId=data["user_id"],
                    apiKey=api_key,
                    apiSecret=api_secret,
                    feedToken=data.get("extended_token"),
                    accessToken=data["access_token"],
                    tokenExpiry=expiry,
                    exchanges=data.get("exchanges", []),
                    products=data.get("products", []),
                    status=data.get("is_active", True)
                ).dict()

                result = await broker_collection.insert_one(broker_doc)
                broker_id = result.inserted_id

            # Link broker to user
            await user_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {"connectedBroker": broker_id},
                    "$addToSet": {"availableBorkerList": broker_id}
                },
                upsert=True
            )

            broker = await broker_collection.find_one({"_id": broker_id})
            return {"broker": broker, "error": None}

        except Exception as e:
            print("Error in get_access_token:", str(e))
            return {"broker": None, "error": str(e)}

    # -------------------
    # 2️⃣ Get User Funds
    # -------------------
    async def get_user_funds(self, broker_id: str):
        broker = await broker_collection.find_one({"_id": ObjectId(broker_id)})
        if not broker:
            raise ValueError("Broker not found. Please connect first.")
        return await self._get("/user/get-funds-and-margin", broker["accessToken"], "Funds could not be retrieved")

    # -------------------
    # 3️⃣ Get User Positions
    # -------------------
    async def get_user_position(self, broker_id: str):
        broker = await broker_collection.find_one({"_id": ObjectId(broker_id)})
        if not broker:
            raise ValueError("Broker not found.")
        return await self._get("/portfolio/short-term-positions", broker["accessToken"], "Positions not retrieved")

    # -------------------
    # 4️⃣ Get User Holdings
    # -------------------
    async def get_user_holdings(self, broker_id: str):
        broker = await broker_collection.find_one({"_id": ObjectId(broker_id)})
        if not broker:
            raise ValueError("Broker not found.")
        return await self._get("/portfolio/long-term-holdings", broker["accessToken"], "Holdings not retrieved")

    # -------------------
    # 5️⃣ Place Order
    # -------------------
    async def place_order(self, broker_id: str, payload: dict):
        broker = await broker_collection.find_one({"_id": ObjectId(broker_id)})
        if not broker:
            raise ValueError("Broker not found.")

        order_data = {
            "quantity": payload.get("quantity"),
            "product": payload.get("product", "D"),
            "validity": payload.get("validity", "DAY"),
            "tag": payload.get("strategyId", "default"),
            "instrument_token": payload.get("symbolId"),
            "order_type": payload.get("orderType"),
            "transaction_type": payload.get("action"),
            "trigger_price": payload.get("trigger_price", 0),
            "is_amo": payload.get("is_amo", False),
            "slice": payload.get("slice", False),
        }

        if payload.get("orderType") == "LIMIT" and payload.get("price"):
            order_data["price"] = payload["price"]

        return await self._post("/order/place", order_data, "Error during place order", broker["accessToken"])

    # -------------------
    # Internal GET Helper
    # -------------------
    async def _get(self, endpoint, auth_token, error_msg):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                res = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers={"Authorization": f"Bearer {auth_token}", "Accept": "application/json"}
                )
                res.raise_for_status()
                return res.json()
            except Exception as e:
                raise ValueError(f"{error_msg}: {str(e)}")

    # -------------------
    # Internal POST Helper
    # -------------------
    async def _post(self, endpoint, body, error_msg, auth_token=None, is_form_urlencoded=False):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                headers = {}
                if is_form_urlencoded:
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                    payload = httpx.QueryParams(body)
                else:
                    headers["Content-Type"] = "application/json"
                    payload = body

                if auth_token:
                    headers["Authorization"] = f"Bearer {auth_token}"    

                res = await client.post(f"{self.base_url}{endpoint}", data=payload if is_form_urlencoded else body, headers=headers)
                res.raise_for_status()
                return res.json()
            except Exception as e:
                raise ValueError(f"{error_msg}: {str(e)}")
