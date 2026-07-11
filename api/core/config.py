from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Elega API"
    environment: str = Field(default="development")
    frontend_origins: list[AnyHttpUrl] = Field(default_factory=list)
    supabase_url: AnyHttpUrl
    supabase_key: str = Field(min_length=1)
    admin_emails: list[str] = Field(default_factory=list)
    admin_registration_secret: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Return allowed CORS origins as strings for FastAPI middleware."""
        return [str(origin).rstrip("/") for origin in self.frontend_origins]

    @property
    def is_production(self) -> bool:
        """Return whether the application is running in production."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
