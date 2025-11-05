from fastapi import FastAPI
from app.routes.strategy_routes import router as strategy_router
from app.routes.order_routes import router as order_router
from app.scheduler.strategy_scheduler import start_scheduler
from app.scheduler.broker_scheduler import calculate_sl_tp
from app.db.init_db import init_db
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio

logger = logging.getLogger("uvicorn")

# --------------------- Lifespan (Startup + Shutdown) --------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # MongoDB initialization
        logger.info("⏳ Connecting to MongoDB...")
        await init_db()
        logger.info("✅ MongoDB connected successfully!")

        # Background tasks
        loop = asyncio.get_event_loop()

        # Start strategy scheduler (Redis + APScheduler)
        loop.create_task(start_scheduler())
        logger.info("📅 Strategy scheduler started in background.")

        # Start SL/TP price watcher in background
        loop.create_task(calculate_sl_tp("6905f6e134e7250e9e8b3389"))
        logger.info("📈 SL/TP background task started.")

        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")

    finally:
        # Clean shutdown logic (optional)
        logger.info("🛑 Shutting down gracefully...")

# --------------------- FastAPI App --------------------- #
app = FastAPI(
    title="Trading API (FastAPI + MongoDB + Redis)",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(strategy_router)
app.include_router(order_router)

# --------------------- Root Endpoint --------------------- #
@app.get("/")
async def root():
    return {"message": "🚀 API is running successfully"}


# --------------------- Local Dev Runner --------------------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=5000, reload=True)
