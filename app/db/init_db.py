from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.strategy_model import Strategy
from app.core.config import setting
import logging


logger = logging.getLogger(__name__)

async def init_db():
    try:
        logger.info("⏳ Connecting to MongoDB...")
        client = AsyncIOMotorClient(setting.MONGO_URI)
        db = client[setting.MONGO_DB]

        await init_beanie(database=db, document_models=[Strategy])
        logger.info("✅ MongoDB connection successful!")

    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
