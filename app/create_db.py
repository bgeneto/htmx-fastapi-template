import asyncio
from .db import init_db
from .logger import get_logger

logger = get_logger("create_db")

if __name__ == '__main__':
    asyncio.run(init_db())
    logger.info("Done creating database (dev).")
