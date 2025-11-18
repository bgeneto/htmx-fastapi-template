from loguru import logger
import sys
from .config import settings

# Basic Loguru configuration. Adjust sinks/format for production.
logger.remove()
logger.add(sys.stdout, level="DEBUG" if settings.debug else "INFO",
           format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level}</level> | <cyan>{name}</cyan> | <level>{message}</level>")

def get_logger(name: str = "app"):
    return logger.bind(module=name)
