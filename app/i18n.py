"""Internationalization utilities for the application with Redis caching."""

from contextvars import ContextVar
from pathlib import Path
import json
from typing import Dict, Any

from babel.support import NullTranslations, Translations

# Store current locale in context variable (thread-safe)
_locale: ContextVar[str] = ContextVar("locale", default="en")

# In-memory cache for loaded translations (fast lookup)
_translations_cache: dict[str, Translations | NullTranslations] = {}

# Path to translations directory
TRANSLATIONS_DIR = Path(__file__).parent.parent / "translations"

# Redis cache for translations (shared across instances)
_translation_redis_cache = None

async def get_translation_redis_cache():
    """Get Redis cache instance for translations."""
    global _translation_redis_cache
    if _translation_redis_cache is None:
        from .redis_utils import template_cache
        _translation_redis_cache = template_cache
    return _translation_redis_cache


def get_locale() -> str:
    """Get the current locale from context."""
    return _locale.get()


def set_locale(locale: str) -> None:
    """Set the current locale in context."""
    _locale.set(locale)


def get_translations(locale: str) -> Translations | NullTranslations:
    """
    Get translations for a given locale with multi-level caching.

    Args:
        locale: The locale code (e.g., 'en', 'pt_BR', 'es')

    Returns:
        Translations object for the locale
    """
    # Check in-memory cache first (fastest)
    if locale in _translations_cache:
        return _translations_cache[locale]

    # Try to load from Redis cache (shared across instances)
    try:
        import asyncio
        from .logger import get_logger
        logger = get_logger(__name__)

        # Create event loop if needed for synchronous context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Try to get from Redis cache
        async def load_from_redis():
            cache = await get_translation_redis_cache()
            cache_key = f"translations:{locale}"

            # Get cached translations data
            cached_data = await cache.get(cache_key)
            if cached_data:
                # Reconstruct translations object from cached data
                translations = Translations.load(
                    dirname=str(TRANSLATIONS_DIR), locales=[locale]
                )
                _translations_cache[locale] = translations
                logger.debug(f"Loaded translations for {locale} from Redis cache")
                return translations

            # Load from disk and cache in Redis
            translations = Translations.load(
                dirname=str(TRANSLATIONS_DIR), locales=[locale]
            )

            # Cache common translations in Redis (serialize key parts)
            common_translations = {}
            if hasattr(translations, '_catalog'):
                # Store a subset of common translations to reduce memory usage
                for key, value in list(translations._catalog.items())[:100]:  # First 100 entries
                    if key and isinstance(key, str) and isinstance(value, str):
                        common_translations[key] = value

            await cache.set(cache_key, {
                "locale": locale,
                "common_translations": common_translations,
                "cached_at": str(Path(__file__).stat().st_mtime)
            }, ttl=3600)  # Cache for 1 hour

            _translations_cache[locale] = translations
            logger.debug(f"Loaded translations for {locale} from disk and cached in Redis")
            return translations

        if loop.is_running():
            # We're in an async context, we can't use async functions here
            # Fall back to synchronous loading
            pass
        else:
            return loop.run_until_complete(load_from_redis())

    except Exception as e:
        from .logger import get_logger
        logger = get_logger(__name__)
        logger.debug(f"Redis cache failed for translations {locale}: {e}")

    # Fallback to synchronous loading
    try:
        _translations_cache[locale] = Translations.load(
            dirname=str(TRANSLATIONS_DIR), locales=[locale]
        )
    except Exception:
        # Fallback to English if locale not found
        _translations_cache[locale] = Translations.load(
            dirname=str(TRANSLATIONS_DIR), locales=["en"]
        )

    return _translations_cache[locale]


def gettext(message: str) -> str:
    """
    Translate a message using the current locale.

    Args:
        message: The message to translate

    Returns:
        Translated message
    """
    locale = get_locale()
    translations = get_translations(locale)
    return translations.gettext(message)


async def invalidate_translation_cache(locale: str = None) -> None:
    """
    Invalidate translation cache for a specific locale or all locales.

    Args:
        locale: Specific locale to invalidate, or None for all locales
    """
    global _translations_cache

    if locale:
        # Clear specific locale from memory cache
        if locale in _translations_cache:
            del _translations_cache[locale]

        # Clear from Redis cache
        try:
            cache = await get_translation_redis_cache()
            await cache.delete(f"translations:{locale}")
        except Exception as e:
            from .logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"Failed to clear Redis cache for locale {locale}: {e}")
    else:
        # Clear all locales from memory cache
        _translations_cache.clear()

        # Clear all from Redis cache
        try:
            cache = await get_translation_redis_cache()
            await cache.delete_pattern("translations:*")
        except Exception as e:
            from .logger import get_logger
            logger = get_logger(__name__)
            logger.debug(f"Failed to clear Redis translation cache: {e}")


# Alias for convenience
_ = gettext
