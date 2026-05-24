"""Application settings, loaded from environment variables.

Using pydantic-settings means env vars are typed and validated.
This is a small thing that pays off in production — typos in env var
names become loud errors at startup instead of silent bugs later.
"""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_origins() -> list[str]:
    """Read CORS_ORIGINS from the env as a comma-separated list.

    Example value: 'https://nba.vercel.app,http://localhost:5173'
    Falls back to a localhost-only default for dev.
    """
    raw = os.environ.get("CORS_ORIGINS", "")
    if not raw.strip():
        return ["http://localhost:5173", "http://localhost:5174"]
    return [o.strip() for o in raw.split(",") if o.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NBA Win Probability Engine"
    environment: str = "development"
    cors_origins: list[str] = _parse_cors_origins()


# A single shared instance — import this everywhere instead of re-reading env.
settings = Settings()