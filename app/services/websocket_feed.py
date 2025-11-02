import asyncio, json, websockets
from datetime import datetime
from app.db.mongodb import db

paper_collection = db["paper_trades"]
broker_collection = db["brokers"]

async def handle_tick(data):
    if "data" not in data:
        return

    for tick in data["data"]:
        token = tick["instrumentKey"]
        ltp = tick.get("ltp")

        trade = await paper_collection.find_one({"symbolToken": token, "isClosed": False})
        if not trade:
            continue

        side = trade["side"]
        sl = trade["stopLoss"]
        tp = trade["targetPrice"]

        if side == "BUY":
            if ltp <= sl:
                await close_paper_trade(trade, ltp, "STOPLOSS")
            elif ltp >= tp:
                await close_paper_trade(trade, ltp, "TARGET")
        else:
            if ltp >= sl:
                await close_paper_trade(trade, ltp, "STOPLOSS")
            elif ltp <= tp:
                await close_paper_trade(trade, ltp, "TARGET")

async def close_paper_trade(trade, ltp, reason):
    pnl = (ltp - trade["entryPrice"]) * trade["quantity"] if trade["side"] == "BUY" else (trade["entryPrice"] - ltp) * trade["quantity"]

    await paper_collection.update_one(
        {"_id": trade["_id"]},
        {"$set": {
            "isClosed": True,
            "exitPrice": ltp,
            "exitTime": datetime.utcnow(),
            "exitReason": reason,
            "pnl": pnl
        }}
    )
    print(f"💥 {reason} triggered for {trade['symbol']} | Exit: {ltp} | PnL: {pnl:.2f}")

async def run_feed():
    broker = await broker_collection.find_one({"status": True})
    if not broker:
        print("❌ No broker found")
        return

    access_token = broker["accessToken"]
    uri = "wss://api.upstox.com/v2/feed/market-data-feed"

    async with websockets.connect(uri, extra_headers={
        "Authorization": f"Bearer {access_token}"
    }) as ws:
        print("✅ Connected to Upstox feed")

        tokens = [trade["symbolToken"] async for trade in paper_collection.find({"isClosed": False})]
        if not tokens:
            print("⚠️ No open paper trades found")
            return

        await ws.send(json.dumps({
            "guid": "feed-001",
            "method": "sub",
            "data": {"mode": "full", "instrumentKeys": tokens}
        }))

        async for msg in ws:
            await handle_tick(json.loads(msg))

