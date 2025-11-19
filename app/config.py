from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    app_name: str = "Alpine.js + Jinja2 + FastAPI Starter"
    ENV: str
    SECRET_KEY: SecretStr
    DATABASE_URL: str
    DEBUG: bool = False
    LOG_FILE: str | None = None

    @property
    def debug(self) -> bool:
        """Alias for DEBUG to maintain compatibility."""
        return self.DEBUG


settings = Settings()
