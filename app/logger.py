import logging
from logging.handlers import TimedRotatingFileHandler
import os

os.makedirs("logs",exist_ok=True)

log_file = "logs/app.log"

file_handler = TimedRotatingFileHandler(log_file, when="midnight",interval=1)
file_handler.suffix ="%Y-%m-%d"
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s- %(message)s")
file_handler.setFormatter(formatter)


logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler,logging.StreamHandler()]
)

logger = logging.getLogger(__name__)
logger.info('Daily file logging initialized successfully!')
