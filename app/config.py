import os

from dotenv import load_dotenv
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    app_name: str = "Alpine.js + Jinja2 + FastAPI Starter"
    ENV: str = Field(...)
    SECRET_KEY: SecretStr = Field(...)
    DATABASE_URL: str = Field(...)
    DEBUG: bool = False
    LOG_FILE: str | None = None

    # Authentication settings
    SESSION_EXPIRY_DAYS: int = 30
    MAGIC_LINK_EXPIRY_MINUTES: int = 15

    # Bootstrap admin (password-based, only admin can use password login)
    BOOTSTRAP_ADMIN_EMAIL: str = Field(...)
    BOOTSTRAP_ADMIN_PASSWORD: SecretStr = Field(...)

    # Login method configuration
    LOGIN_METHOD: str = "otp"  # Options: magic, otp, classic
    OTP_EXPIRY_MINUTES: int = 5

    # Default role for new users (pending, user, moderator, admin)
    DEFAULT_USER_ROLE: str = "pending"

    @field_validator("DEFAULT_USER_ROLE")
    @classmethod
    def validate_default_role(cls, v: str) -> str:
        valid_roles = ["pending", "user", "moderator", "admin"]
        if v.lower() not in valid_roles:
            raise ValueError(f"Invalid default role: {v}. Must be one of {valid_roles}")
        return v.lower()

    # If True: new users are created as active USER role (instant access)
    AUTO_REGISTRATION: bool = True

    # Email settings (Resend)
    EMAIL_API_KEY: SecretStr = Field(...)
    EMAIL_FROM_ADDRESS: str = Field(...)
    EMAIL_FROM_NAME: str = "Alpine FastAPI"

    # Application base URL for magic links
    APP_BASE_URL: str = Field(...)

    # Internationalization (i18n) settings
    # Set to False to disable translations and show only default language (single language mode)
    # When disabled, all UI text and validation messages will use the default language
    ENABLE_I18N: bool = True

    # Application version for footer/about pages
    APP_VERSION: str = "1.0.0"

    @property
    def debug(self) -> bool:
        """Alias for DEBUG to maintain compatibility."""
        return self.DEBUG


# Instantiate Settings from environment with sane defaults for local development/testing.
# Required fields will prefer environment/.env values but fall back to safe defaults to avoid
# import-time errors in static analysis or during tooling runs.
settings = Settings(
    ENV=os.getenv("ENV", "development"),
    SECRET_KEY=SecretStr(os.environ["SECRET_KEY"]),  # Must be set in env
    DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db"),
    BOOTSTRAP_ADMIN_EMAIL=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com"),
    BOOTSTRAP_ADMIN_PASSWORD=SecretStr(
        os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")  # Must be set in env
    ),
    LOGIN_METHOD=os.getenv("LOGIN_METHOD", "otp"),
    OTP_EXPIRY_MINUTES=int(os.getenv("OTP_EXPIRY_MINUTES", "5")),
    DEFAULT_USER_ROLE=os.getenv("DEFAULT_USER_ROLE", "pending"),
    AUTO_REGISTRATION=os.getenv("AUTO_REGISTRATION", "true").lower() == "true",
    EMAIL_API_KEY=SecretStr(os.getenv("EMAIL_API_KEY", "")),
    EMAIL_FROM_ADDRESS=os.getenv("EMAIL_FROM_ADDRESS", "noreply@example.com"),
    APP_BASE_URL=os.getenv("APP_BASE_URL", "http://localhost:8000"),
)
