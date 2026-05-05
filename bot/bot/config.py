from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, FrozenSet

from dotenv import load_dotenv

from .logging_setup import setup_logging


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_int(key: str, default: Optional[int] = None) -> Optional[int]:
    v = _env(key, "")
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _parse_int_set(value: str) -> FrozenSet[int]:
    items = []
    for x in (value or "").split(","):
        x = x.strip()
        if not x:
            continue
        if x.isdigit():
            items.append(int(x))
    return frozenset(items)


def _parse_str_tuple(value: str) -> Tuple[str, ...]:
    return tuple(x.strip() for x in (value or "").split(",") if x.strip())


# Load .env once (idempotent)
load_dotenv(override=False)

# Setup centralized logger once
logger = setup_logging(level=logging.INFO)


@dataclass(frozen=True, slots=True)
class Settings:
    # Core
    bot_token: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    deepseek_api_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY"))
    deepseek_base_url: str = field(default_factory=lambda: _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"))
    deepseek_model: str = field(default_factory=lambda: _env("DEEPSEEK_MODEL", "deepseek-chat"))

    # Storage
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "postgresql+asyncpg://yozuvchim:changeme@postgres:5432/yozuvchim"))
    data_dir: str = field(default_factory=lambda: _env("DATA_DIR", "./data"))
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://localhost:6379/0"))
    redis_queue_name: str = field(default_factory=lambda: _env("REDIS_QUEUE_NAME", "academic_bot_queue"))

    # Failover / Secondary AI
    secondary_ai_api_key: str = field(default_factory=lambda: _env("SECONDARY_AI_API_KEY", ""))
    secondary_ai_base_url: str = field(default_factory=lambda: _env("SECONDARY_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/"))
    secondary_ai_model: str = field(default_factory=lambda: _env("SECONDARY_AI_MODEL", "gpt-4o"))

    # Payments / Plans
    bot_username: str = field(default_factory=lambda: _env("BOT_USERNAME", ""))
    currency: str = field(default_factory=lambda: _env("CURRENCY", "UZS"))

    # Admin / Access — superadmins from env (irrevocable bootstrap admins)
    admin_ids: FrozenSet[int] = field(default_factory=lambda: _parse_int_set(_env("SUPERADMIN_IDS", "")))
    required_channels: Tuple[str, ...] = field(default_factory=lambda: _parse_str_tuple(_env("REQUIRED_CHANNELS", "")))

    # Results channel: can be channel id (-100...) or @username-like
    # Recommend using numeric channel_id in production.
    results_channel: str = field(default_factory=lambda: _env("RESULTS_CHANNEL", ""))

    # Image API (Unsplash — bepul, slaydlar uchun)
    unsplash_api_key: str = field(default_factory=lambda: _env("UNSPLASH_API_KEY", ""))

    # Bot behavior
    skip_updates: bool = field(default_factory=lambda: _env("SKIP_UPDATES", "1") in ("1", "true", "True", "YES", "yes"))
    ai_timeout_sec: int = field(default_factory=lambda: int(_env("AI_TIMEOUT_SEC", "240")))
    export_timeout_sec: int = field(default_factory=lambda: int(_env("EXPORT_TIMEOUT_SEC", "60")))
    max_retries: int = field(default_factory=lambda: int(_env("MAX_RETRIES", "2")))
    retry_backoff_sec: int = field(default_factory=lambda: int(_env("RETRY_BACKOFF_SEC", "2")))

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.deepseek_api_key:
            missing.append("DEEPSEEK_API_KEY")

        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        # Ensure folders exist
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

        # Log summary (do NOT print secrets)
        logger.info(
            "Config loaded: db=%s, data_dir=%s, admins=%d, required_channels=%d, results_channel=%s",
            self.database_url,
            self.data_dir,
            len(self.admin_ids),
            len(self.required_channels),
            self.results_channel or "(none)",
        )

    def validate_or_raise(self):
        """Ensures critical settings are present or logs massive warnings."""
        if not self.bot_token:
            logger.critical("BOT_TOKEN is missing! Bot cannot start.")
            raise ValueError("BOT_TOKEN missing")
        if not self.deepseek_api_key:
            logger.warning("DEEPSEEK_API_KEY is missing! AI features will fail.")


# Singleton instance
SETTINGS = Settings()
SETTINGS.validate_or_raise()
