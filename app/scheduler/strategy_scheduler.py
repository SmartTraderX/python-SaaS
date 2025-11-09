import inspect
import asyncio
import logging
from datetime import datetime
from redis import asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.strategy_model import Strategy
from app.services.strategy_evalutation_services import EvaluteStrategy

from app.logger import logger

# async def checkResult (str = None):

#     if str == None:
#         return 
    

async def process_queue(timeframe):
    """
    Process a batch of strategy evaluations for the given timeframe.
    If strategy condition is False, re-enqueue it for next round.
    """
    try:
        logger.info(f"[{timeframe}] Worker started.")
        # Use await and convert to list
        strategies = await Strategy.find({"timeframe": timeframe , "status":True}).to_list()
        if not strategies:
            logger.info(f"No strategies found for timeframe {timeframe}")
            return

        for strategy in strategies:
            try:
                # ⚙️ Evaluate this strategy
                result = EvaluteStrategy(strategy)
                # await checkResult(result)   # optional future step
            except Exception as e:
                logger.error(f"Error evaluating strategy {strategy.strategyName}: {e}")

    except Exception as e:
        logger.error(f"[{timeframe}] Worker error: {e}", exc_info=True)
    finally:
        logger.info(f"[{timeframe}] Processed strategies.")

# scheduler startup function (unchanged)
async def start_scheduler():
    scheduler = AsyncIOScheduler()
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=1), args=["1m"])
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=3), args=["3m"])
    scheduler.add_job(process_queue, IntervalTrigger(minutes=5), args=["5m"])
    scheduler.add_job(process_queue, IntervalTrigger(minutes=15), args=["15m"])
    scheduler.start()
    logger.info(" APScheduler started successfully.")
