from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys


# Make app folder visible for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.user_model import UserModel
from models.strategy_model import Strategy
from models.paper_trade_model import Paper_Trade
from models.user_model import UserModel
# from core.config import setting
from redis.asyncio import Redis
from app.logger import logger

async def init_db():
    try:
        logger.info("Connecting to MongoDB...")
        client = AsyncIOMotorClient("mongodb+srv://vishalgarna:vishalgarna%401@cluster0.uxsnu.mongodb.net")
        db = client["Saas"]

        await init_beanie(database=db, document_models=[Strategy , Paper_Trade , UserModel])
        logger.info("MongoDB connection successful!")

    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")

async def init_redis():
    try:
        logger.info('redis connecting...')
        redis = Redis.from_url(REDIS_URL)
        logger.info('redis connected')
        return redis

    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")    
