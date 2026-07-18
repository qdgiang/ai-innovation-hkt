"""Env contract — architecture.md §Configuration. `pydantic-settings` loads it;
`infra/.env.example` is the documented contract; `.env` is git-ignored.
"""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://evermind:evermind@localhost:5432/evermind"

    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-v4-flash"
    ai_api_key: str = ""

    extraction_batch_size: int = 25  # max messages per extraction window
    # ING beat cadence in SECONDS (0 disables); a window is only cut once the
    # newest pending message is at least SETTLE_SEC old, so an
    # actively-flowing conversation is never split mid-thought.
    extraction_interval_sec: int = 10
    extraction_settle_sec: int = 15
    extraction_max_wait_sec: int = 60
    confidence_tau: float = 0.8
    org_timezone: str = "Asia/Ho_Chi_Minh"

    telegram_bot_token: str = ""
    # CAP-4 live capture beat; needs a bot token too — 0 disables the loop.
    telegram_poll_ms: int = 2000
    replay_pace_ms: int = 800
    grace_window_min: int = 10
    nudge_after_hours: int = 48

    # P4 glue: the in-app projection-consumer loop + APScheduler (OPS-4).
    # 0 disables the loop (tests drive consumers explicitly).
    consumer_poll_ms: int = 2000
    run_scheduler: bool = True

    @model_validator(mode="after")
    def extraction_wait_is_valid(self):
        if self.extraction_interval_sec < 0:
            raise ValueError("EXTRACTION_INTERVAL_SEC must be >= 0")
        if self.extraction_settle_sec < 0:
            raise ValueError("EXTRACTION_SETTLE_SEC must be >= 0")
        if self.extraction_max_wait_sec < 0:
            raise ValueError("EXTRACTION_MAX_WAIT_SEC must be >= 0")
        if self.extraction_max_wait_sec < self.extraction_settle_sec:
            raise ValueError("EXTRACTION_MAX_WAIT_SEC must be >= EXTRACTION_SETTLE_SEC")
        return self


settings = Settings()
