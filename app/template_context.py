"""
Template context helpers for common context data
"""

from datetime import datetime

from app.config import settings


def get_footer_context() -> dict:
    """
    Get common footer context variables for all templates.

    Returns:
        dict: Dictionary with footer context containing:
            - app_version: Application version
            - environment: Current environment (development, staging, production)
            - current_year: Current year for copyright notice
    """
    return {
        "app_version": getattr(settings, "APP_VERSION", "1.0.0"),
        "environment": settings.ENV.lower(),
        "current_year": datetime.now().year,
    }
