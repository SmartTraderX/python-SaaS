from fastapi import FastAPI
from app.routes.strategy_routes import router as strategy_router
from app.scheduler.strategy_scheduler import start_scheduler
from app.db.init_db import init_db  # Make sure you have a shutdown function
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio

logger = logging.getLogger("uvicorn")

# Lifespan context manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("⏳ Connecting to MongoDB...")
        await init_db()
        logger.info("✅ MongoDB connected successfully!")
        asyncio.create_task(start_scheduler())
        yield
    finally:
        # Shutdown code
        if "close_db_connection" in globals():
            # await close_db_connection()
            logger.info("🛑 MongoDB connection closed")

# Create FastAPI app with lifespan
app = FastAPI(title="Trading API with FastAPI + MongoDB", lifespan=lifespan)

# Include routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(strategy_router)

@app.get("/")
async def root():
    return {"message": "API is running"}

# Only start Uvicorn server if this file is run directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=5000, reload=True)
