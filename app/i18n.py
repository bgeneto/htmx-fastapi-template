"""Internationalization utilities for the application."""

from contextvars import ContextVar
from pathlib import Path

from babel.support import NullTranslations, Translations

# Store current locale in context variable (thread-safe)
_locale: ContextVar[str] = ContextVar("locale", default="en")

# Cache for loaded translations
_translations_cache: dict[str, Translations | NullTranslations] = {}

# Path to translations directory
TRANSLATIONS_DIR = Path(__file__).parent.parent / "translations"


def get_locale() -> str:
    """Get the current locale from context."""
    return _locale.get()


def set_locale(locale: str) -> None:
    """Set the current locale in context."""
    _locale.set(locale)


def get_translations(locale: str) -> Translations | NullTranslations:
    """
    Get translations for a given locale.

    Args:
        locale: The locale code (e.g., 'en', 'pt_BR', 'es')

    Returns:
        Translations object for the locale
    """
    if locale not in _translations_cache:
        try:
            _translations_cache[locale] = Translations.load(
                dirname=str(TRANSLATIONS_DIR), locales=[locale]
            )
        except Exception:
            # Fallback to NullTranslations if locale not found
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


# Alias for convenience
_ = gettext
