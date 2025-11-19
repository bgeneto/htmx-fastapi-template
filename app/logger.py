import sys
from pathlib import Path

from loguru import logger

from .config import settings

# Remove default handler
logger.remove()

# Determine log level based on DEBUG setting
log_level = "DEBUG" if settings.DEBUG else "INFO"


# Format function that handles missing 'module' in extra
def format_record(record):
    record["extra"].setdefault("module", "app")
    return True


log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{extra[module]: <20}</cyan> | <level>{message}</level>"

# Console output
logger.add(
    sys.stdout,
    level=log_level,
    format=log_format,
    colorize=True,
    filter=format_record,
)

# File output (if LOG_FILE is configured)
if settings.LOG_FILE:
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        settings.LOG_FILE,
        level=log_level,
        format=log_format,
        rotation="10 MB",  # Rotate when file reaches 10MB
        retention="7 days",  # Keep logs for 7 days
        compression="zip",  # Compress rotated logs
        enqueue=True,  # Thread-safe logging
        filter=format_record,
    )
    logger.info(f"File logging enabled: {settings.LOG_FILE}")


def get_logger(name: str = "app"):
    return logger.bind(module=name)
