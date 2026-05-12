"""Application settings, loaded from environment variables.

Using pydantic-settings means env vars are typed and validated.
This is a small thing that pays off in production — typos in env var
names become loud errors at startup instead of silent bugs later.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NBA Win Probability Engine"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]


# A single shared instance — import this everywhere instead of re-reading env.
settings = Settings()