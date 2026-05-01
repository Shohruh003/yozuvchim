from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from cachetools import TTLCache
import time


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(
        self,
        time_limit: float = 0.5,
        notify: bool = True,
    ) -> None:
        self.cache = TTLCache(maxsize=50_000, ttl=time_limit)
        self.notify = notify

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Safety check
        if not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        chat_id = event.chat.id if event.chat else user_id

        # Key per user per chat (important!)
        key = f"{chat_id}:{user_id}"

        if key in self.cache:
            if self.notify:
                # Juda ko‘p xabar bermaslik uchun
                now = time.time()
                last_warn = self.cache.get(f"warn:{key}")
                if not last_warn:
                    self.cache[f"warn:{key}"] = now
                    await event.answer("⏳ Iltimos, biroz sekinroq yuboring.")
            return

        self.cache[key] = True
        return await handler(event, data)
