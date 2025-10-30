from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.strategy_model import Strategy
from app.models.paper_trade_model import Paper_Trade
from app.models.user_model import UserModel
from app.core.config import setting
from redis.asyncio import Redis
import logging


logger = logging.getLogger(__name__)

async def init_db():
    try:
        logger.info("⏳ Connecting to MongoDB...")
        client = AsyncIOMotorClient(setting.MONGO_URI)
        db = client[setting.MONGO_DB]

        await init_beanie(database=db, document_models=[Strategy , Paper_Trade , UserModel])
        logger.info("✅ MongoDB connection successful!")

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
