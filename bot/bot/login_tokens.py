"""One-time login tokens stored in Redis.

The NestJS backend reads tokens with the same key prefix
(`login_token:<token>`) so the bot and backend stay in sync without
needing to share Python code with each other.
"""
from __future__ import annotations

import secrets

from redis.asyncio import Redis

from .config import SETTINGS

KEY_PREFIX = "login_token:"
TTL_SECONDS = 3600  # 1 hour

_redis: Redis | None = None


def _client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(SETTINGS.redis_url, decode_responses=True)
    return _redis


async def make_token(user_id: int) -> str:
    """Issue a fresh one-time login token for the given Telegram user id."""
    token = secrets.token_urlsafe(24)
    await _client().set(KEY_PREFIX + token, str(user_id), ex=TTL_SECONDS)
    return token
