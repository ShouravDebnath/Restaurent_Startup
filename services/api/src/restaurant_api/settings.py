from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://db"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    session_idle_seconds: int = Field(default=1800, ge=1, le=1800)
    session_absolute_seconds: int = Field(default=28800, ge=1, le=28800)
    cookie_secure: bool = False
    demo_mode: bool = True

    @model_validator(mode="after")
    def require_secure_deployment(self):
        if self.app_env != "development" and not self.cookie_secure:
            raise ValueError("HTTPS secure cookies are required outside local development")
        if not self.origins:
            raise ValueError("Configure at least one exact allowed origin")
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Configure exact HTTP(S) origins without paths or credentials")
            if self.app_env != "development" and parsed.scheme != "https":
                raise ValueError("HTTPS allowed origins are required outside local development")
        return self

    @property
    def cookie_name(self) -> str:
        return "__Host-restaurant_session" if self.cookie_secure else "restaurant_session"

    @property
    def origins(self) -> set[str]:
        return {value.strip() for value in self.allowed_origins.split(",") if value.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
