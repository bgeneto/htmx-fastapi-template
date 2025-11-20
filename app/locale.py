from typing import Optional, Protocol

from starlette.requests import Request


class LocaleDetector(Protocol):
    """Protocol for detecting locale from a request."""

    def detect(self, request: Request) -> Optional[str]:
        """Detect locale from request. Returns None if not found."""
        ...


class CookieLocaleDetector:
    """Detect locale from cookie."""

    def detect(self, request: Request) -> Optional[str]:
        return request.cookies.get("locale")


class HeaderLocaleDetector:
    """Detect locale from Accept-Language header."""

    def __init__(self):
        self.default_locale = "en"

    def detect(self, request: Request) -> Optional[str]:
        accept_language = request.headers.get("Accept-Language", self.default_locale)
        # Parse Accept-Language header (simple parsing)
        locale = accept_language.split(",")[0].split(";")[0].strip()
        # Normalize locale (e.g., en-US -> en, pt-BR -> pt_BR)
        if "-" in locale:
            parts = locale.split("-")
            if len(parts[1]) == 2 and parts[1].isupper():
                # Country code: pt-BR -> pt_BR
                locale = f"{parts[0]}_{parts[1]}"
            else:
                # Language only: en-US -> en
                locale = parts[0]
        return locale


class LocaleResolver:
    """Resolves locale using multiple detection strategies."""

    def __init__(self, detectors: list[LocaleDetector]):
        self.detectors = detectors

    def resolve_locale(self, request: Request) -> str:
        """Try each detector until one returns a locale."""
        for detector in self.detectors:
            locale = detector.detect(request)
            if locale:
                return locale
        return "en"  # fallback


# Default resolver instance
default_locale_resolver = LocaleResolver(
    [
        CookieLocaleDetector(),
        HeaderLocaleDetector(),
    ]
)
