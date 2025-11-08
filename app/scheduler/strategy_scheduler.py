import inspect
import asyncio
import logging
from datetime import datetime
from redis import asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.strategy_model import Strategy
from app.services.strategy_evalutation_services import EvaluteStrategy

logger = logging.getLogger(__name__)

TIMEFRAMES = ["5m", "15m"]
REDIS_URL = "redis://localhost:6379"
redis = None


async def init_redis():
    global redis
    try:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis.ping()
        logger.info("Redis connected successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed ({e}). Continuing without Redis.")
        redis = None


async def initial_load():
    """
    Enqueue all active (or inactive but schedulable) strategies into Redis queues once at startup.
    """
    if not redis:
        logger.warning("Redis not connected — skipping initial load.")
        return

    logger.info("Running initial load: fetching strategies from DB...")

    try:
        # Get all active or pending strategies (adjust your query condition)
        all_strategies = await Strategy.find(
            Strategy.status == False  # or True depending on your logic
        ).to_list()

        if not all_strategies:
            logger.info("No strategies found for initial load.")
            return

        for strat in all_strategies:
            timeframe = getattr(strat, "timeframe", None)
            if timeframe in TIMEFRAMES:
                await enqueue_strategy(strat.id, timeframe)
            else:
                logger.warning(f"Strategy {strat.id} has invalid timeframe: {timeframe}")

        logger.info(f"Initial load complete: {len(all_strategies)} strategies enqueued.")
    except Exception as e:
        logger.error(f"Initial load error: {e}")


async def enqueue_strategy(strategy_id: str, timeframe: str):
    """
    Enqueue strategy_id for a given timeframe, but only if it's not already queued.
    Uses a Redis set for idempotency: queue:set:{tf}
    """
    if not redis:
        logger.warning("Redis not connected — skipping enqueue.")
        return False

    list_key = f"queue:{timeframe}"
    set_key = f"queue:set:{timeframe}"

    try:
        # Try to add to set. SADD returns 1 if newly added, 0 if already present.
        added = await redis.sadd(set_key, str(strategy_id))
        if added:
            # newly added to set -> push to list for processing
            await redis.rpush(list_key, str(strategy_id))
            logger.info(f"{datetime.now()}: Enqueued strategy {strategy_id} to {timeframe} queue")
            return True
        else:
            logger.debug(f"{strategy_id} already queued for {timeframe}, skipping enqueue.")
            return False
    except Exception as e:
        logger.error(f"Failed to enqueue {strategy_id} for {timeframe}: {e}")
        return False
    
async def process_queue(timeframe):
    """
    Process a batch of strategy evaluations for the given timeframe.
    If strategy condition is False, re-enqueue it for next round.
    """
    if not redis:
        logger.warning(f"[{timeframe}] Redis not connected — skipping processing.")
        return

    key = f"queue:{timeframe}"
    processed = 0

    try:
        logger.info(f"[{timeframe}] Worker started.")
        for _ in range(20):
            strategy_id = await redis.lpop(key)
            if not strategy_id:
                break

            strategy = await Strategy.get(strategy_id)
            if not strategy:
                logger.warning(f"[{timeframe}] Strategy {strategy_id} not found.")
                continue

            try:
                result = await EvaluteStrategy(strategy, True)
                processed += 1
                logger.info(f"[{timeframe}] Strategy {strategy_id} evaluated → {result}")

                # 🧠 If not triggered → push back to queue for next evaluation
                await enqueue_strategy(strategy.id, timeframe)

            except Exception as inner_e:
                logger.error(f"[{timeframe}] Eval error for {strategy_id}: {inner_e}")

    except Exception as e:
        logger.error(f"[{timeframe}] Worker error: {e}")
    finally:
        logger.info(f"[{timeframe}] Processed {processed} strategies.")


# scheduler startup function (unchanged)
async def start_scheduler():
    await init_redis()
    # do not run initial_load here if you prefer queue-only operation.
    # if you still want initial load (enqueue pending DB strategies once), implement it using enqueue_strategy
    await initial_load()

    scheduler = AsyncIOScheduler()
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=1), args=["1m"])
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=3), args=["3m"])
    scheduler.add_job(process_queue, IntervalTrigger(minutes=5), args=["5m"])
    scheduler.add_job(process_queue, IntervalTrigger(minutes=15), args=["15m"])
    scheduler.start()
    logger.info(" APScheduler started successfully.")
