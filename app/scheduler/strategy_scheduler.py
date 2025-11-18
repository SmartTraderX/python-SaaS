import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import threading
from app.strategies.swing_trend_volume import (swingHigh_volume_trend_rsi_buy, swingLow_volume_trend_rsi_buy)
from app.logger import logger


# async def checkResult (str = None):

#     if str == None:
#         return 
volatile_symbols = ["SBIN", "RELIANCE", "HDFCBANK", "TATAMOTORS", "LT", "INFY", "TCS", "MARUTI", "TATASTEEL", "JSWSTEEL",
           "ADANIENT", "ADANIPORTS", "ADANIPOWER", "AXISBANK", "BAJFINANCE", "BAJAJFINSV", "ULTRACEMCO", "HINDALCO",
           "ICICIBANK", "BAJAJELEC"] 

up_trend_symbols = ["SBIN", "RELIANCE", "HDFCBANK"] 

down_trend_symbols = [" INFY","TCS"]


def run_in_async_thread(coro , *args):
    return asyncio.run(coro(*args))

def worker_up(symbols, timframe):
    threads = []

    for sym in symbols:
        t = threading.Thread(target=run_in_async_thread , args=(swingLow_volume_trend_rsi_buy,sym, timframe))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()    
      
def worker_down(symbols, timeframe):
    threads = []
    for sym in symbols:
        t = threading.Thread(
            target=run_in_async_thread,
            args=(swingHigh_volume_trend_rsi_buy ,sym, timeframe)
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
async def process_queue(timeframe):
    """
    Process a batch of strategy evaluations for the given timeframe.
    If strategy condition is False, re-enqueue it for next round.
    """
    try:
        logger.info(f"[{timeframe}] Worker started.")
        # Use await and convert to list

        loop = asyncio.get_running_loop()

        await asyncio.gather(
            loop.run_in_executor(None,worker_up , up_trend_symbols, timeframe),
            # loop.run_in_executor(None, worker_down,down_trend_symbols , timeframe)
        )
        print(f'All Threads is completed for this timeframe{timeframe}')

    except Exception as e:
        logger.error(f"[{timeframe}] Worker error: {e}", exc_info=True)
    finally:
        logger.info(f"[{timeframe}] Processed strategies.")

# scheduler startup function (unchanged)
async def start_scheduler():
    scheduler = AsyncIOScheduler()
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=1), args=["1m"])
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=3), args=["3m"])
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=5), args=["5m"])
    scheduler.add_job(process_queue, IntervalTrigger(minutes=15), args=["15m"])
    # scheduler.add_job(process_queue, IntervalTrigger(minutes=60), args=["1h"])
    scheduler.start()
    logger.info(" APScheduler started successfully.")


