"""Env-based settings. Variable names are contract — see ai-docs/deployment.md."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///data/dev.db"

    deepseek_api_key: str = ""
    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-v4-flash"  # NOT deepseek-chat (retired 2026-07-24)

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    app_base_url: str = "http://localhost:8000"
    bot_mode: Literal["polling", "webhook"] = "polling"

    api_shared_token: str = ""


settings = Settings()
