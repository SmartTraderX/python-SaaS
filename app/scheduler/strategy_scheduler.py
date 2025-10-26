from app.db.init_db import init_redis
from app.models.strategy_model import Strategy
from app.services.strategy_evalutation_services import EvaluteStrategy
import asyncio
from datetime import datetime

import logging

logger = logging.getLogger(__name__)
TIMEFRAMES = ["1m", "5m", "15m"]

redis = init_redis()


# ---------------- Queue ---------------- #
async def enqueue_strategy(strategy_id, timeframe):
    key = f"queue:{timeframe}"
    await redis.rpush(key, str(strategy_id))
    logger.info(f"{datetime.now()}: Enqueued strategy {strategy_id} to {timeframe} queue")


async def worker(timeframe):
    key = f"queue:{timeframe}"
    while True:
        item = await redis.blpop(key, timeout=5)
        if item:
            _, strategy_id = item
            strategy = await Strategy.get(strategy_id.decode())
            if strategy:
                await EvaluteStrategy(strategy)

# ---------------- Initial DB Load ---------------- #
async def initial_load():
    """Load existing PENDING strategies from DB into Redis queues"""
    for tf in TIMEFRAMES:
        strategies = await Strategy.find(
            Strategy.status == False,
            Strategy.timeframe == tf
        ).to_list()
        for strat in strategies:
            await enqueue_strategy(strat.id, tf)
    logger.info("Initial load completed: PENDING strategies enqueued")

# ---------------- MongoDB Watch ---------------- #
async def watch_new_strategies():
    """Watch MongoDB insert and push to Redis queues"""
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.core.config import setting

    client = AsyncIOMotorClient(setting.MONGO_URI)
    db = client[setting.MONGO_DB]
    collection = db.strategy

    async with collection.watch([{"$match": {"operationType": "insert"}}]) as stream:
        async for change in stream:
            new_strategy = change["fullDocument"]
            tf = new_strategy.get("timeframe")
            if tf in TIMEFRAMES:
                strategy_doc = await Strategy.get(new_strategy["_id"])
                await enqueue_strategy(strategy_doc.id, tf)

# ---------------- Start Scheduler ---------------- #
async def start_scheduler():
    """Start workers for all timeframes + initial DB load + MongoDB watcher"""
    await initial_load()
    loop = asyncio.get_event_loop()
    for tf in TIMEFRAMES:
        loop.create_task(worker(tf))
    loop.create_task(watch_new_strategies())
    logger.info("Redis multi-timeframe scheduler started")

