"""
URL validation utilities for security and safety

This module provides centralized URL validation to prevent security issues
like open redirects and unauthorized access to sensitive endpoints.
"""

from urllib.parse import unquote, urlparse


class RedirectUrlValidator:
    """Validates redirect URLs for security"""

    # Sensitive endpoints that should never be auto-redirected to
    SENSITIVE_ENDPOINTS = {
        "/admin/logout",
        "/admin/login",
        "/auth/logout",
        "/auth/login",
        "/admin/users/delete",
        "/admin/users/{user_id}/delete",
        "/admin/contact/delete",
    }

    # Allowed path prefixes for redirects
    ALLOWED_PREFIXES = {
        "/admin",
        "/",
    }

    @classmethod
    def validate_admin_redirect(cls, url: str, default_url: str = "/admin") -> str:
        """
        Validate and normalize admin redirect URL

        Args:
            url: The URL to validate
            default_url: Fallback URL if validation fails

        Returns:
            Validated URL or default_url if invalid
        """
        if not url:
            return default_url

        try:
            decoded = unquote(url)
            parsed = urlparse(decoded)

            # Security validation
            if cls._is_safe_redirect(parsed):
                return decoded

        except Exception:
            # If URL parsing fails, use default
            pass

        return default_url

    @classmethod
    def validate_auth_redirect(cls, url: str, default_url: str = "/") -> str:
        """
        Validate and normalize general auth redirect URL

        Args:
            url: The URL to validate
            default_url: Fallback URL if validation fails

        Returns:
            Validated URL or default_url if invalid
        """
        if not url:
            return default_url

        try:
            decoded = unquote(url)
            parsed = urlparse(decoded)

            # Security validation for general redirects
            if cls._is_safe_general_redirect(parsed):
                return decoded

        except Exception:
            # If URL parsing fails, use default
            pass

        return default_url

    @classmethod
    def _is_safe_redirect(cls, parsed) -> bool:
        """
        Check if parsed URL is safe for admin redirects

        Args:
            parsed: Parsed URL result from urlparse

        Returns:
            True if URL is safe, False otherwise
        """
        # Must be relative URL (no scheme or netloc)
        if parsed.scheme or parsed.netloc:
            return False

        # Path must start with allowed prefix
        if not any(parsed.path.startswith(prefix) for prefix in cls.ALLOWED_PREFIXES):
            return False

        # Path must not be in sensitive endpoints
        if parsed.path in cls.SENSITIVE_ENDPOINTS:
            return False

        # Check for path traversal attempts
        if ".." in parsed.path:
            return False

        return True

    @classmethod
    def _is_safe_general_redirect(cls, parsed) -> bool:
        """
        Check if parsed URL is safe for general redirects

        Args:
            parsed: Parsed URL result from urlparse

        Returns:
            True if URL is safe, False otherwise
        """
        # Must be relative URL (no scheme or netloc)
        if parsed.scheme or parsed.netloc:
            return False

        # Path must not have dangerous characters
        dangerous_chars = ["<", ">", '"', "'", "javascript:", "data:"]
        if any(char in parsed.path.lower() for char in dangerous_chars):
            return False

        # Check for path traversal attempts
        if ".." in parsed.path:
            return False

        # Must not point to external sites
        if parsed.path.startswith("http://") or parsed.path.startswith("https://"):
            return False

        return True


class UrlValidator:
    """General URL validation utilities"""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Basic URL validation

        Args:
            url: URL to validate

        Returns:
            True if URL appears valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def is_safe_path(path: str) -> bool:
        """
        Validate that a path is safe for internal use

        Args:
            path: Path to validate

        Returns:
            True if path is safe, False otherwise
        """
        if not path:
            return False

        # Check for path traversal
        if ".." in path:
            return False

        # Check for null bytes
        if "\x00" in path:
            return False

        # Check for dangerous characters
        dangerous = ["<", ">", "|", "&", ";", "`", "$"]
        if any(char in path for char in dangerous):
            return False

        return True

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Normalize a file system path

        Args:
            path: Path to normalize

        Returns:
            Normalized path
        """
        if not path:
            return "/"

        # Remove multiple slashes
        while "//" in path:
            path = path.replace("//", "/")

        # Remove trailing slash (except for root)
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        return path


# Convenience functions for common validation patterns
def validate_admin_redirect(url: str, default_url: str = "/admin") -> str:
    """Shortcut for admin redirect validation"""
    return RedirectUrlValidator.validate_admin_redirect(url, default_url)


def validate_auth_redirect(url: str, default_url: str = "/") -> str:
    """Shortcut for auth redirect validation"""
    return RedirectUrlValidator.validate_auth_redirect(url, default_url)


def is_safe_path(path: str) -> bool:
    """Shortcut for path safety validation"""
    return UrlValidator.is_safe_path(path)
