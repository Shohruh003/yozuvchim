import asyncio
import json
from typing import Optional, Dict, List, Set
import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError
from .config import SETTINGS, logger


class AIQueueClosed(RuntimeError):
    pass


class AIQueue:
    """
    Hybrid Queue: Redis-backed (Production) OR In-Memory (Dev/Fallback).
    
    Features:
    - Auto-detects if Redis is available.
    - Falls back to asyncio.Queue if Redis fails.
    - Supports ack/nack (simulated in memory).
    """

    def __init__(self):
        self._mode = "unknown"  # "redis" or "memory"
        
        # Redis state
        self._redis: Optional[redis.Redis] = None
        self._queue_key = SETTINGS.redis_queue_name
        self._seen_key = f"{SETTINGS.redis_queue_name}:seen"
        self._inflight_key = f"{SETTINGS.redis_queue_name}:inflight"
        
        # Memory state
        self._local_queue: Optional[asyncio.Queue] = None
        self._local_seen: Set[int] = set()
        self._local_inflight: Set[int] = set()
        
        self._closed = False

    async def connect(self):
        """Attempts to connect to Redis. Falls back to memory if failed."""
        if self._mode != "unknown":
            return

        try:
            logger.info(f"AIQueue: Connecting to Redis at {SETTINGS.redis_url}...")
            r = redis.from_url(SETTINGS.redis_url, decode_responses=True, socket_connect_timeout=2)
            await r.ping()
            self._redis = r
            self._mode = "redis"
            logger.info("AIQueue: Successfully connected to Redis.")
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"AIQueue: Redis connection failed ({e}). Switching to IN-MEMORY mode.")
            self._mode = "memory"
            self._local_queue = asyncio.Queue()
            self._local_seen = set()
            self._local_inflight = set()

    async def disconnect(self):
        if self._redis:
            await self._redis.close()
            self._redis = None
        self._mode = "unknown"

    async def put(self, req_id: int) -> bool:
        if req_id is None or req_id <= 0:
            return False
        if self._closed:
            raise AIQueueClosed("AIQueue is closed")
        
        if self._mode == "unknown":
            await self.connect()

        if self._mode == "redis":
            try:
                is_new = await self._redis.sadd(self._seen_key, str(req_id))
                if not is_new:
                    return False
                await self._redis.rpush(self._queue_key, str(req_id))
                return True
            except (ConnectionError, TimeoutError) as e:
                logger.error("AIQueue: Redis connection failed during put(req_id=%s): %s", req_id, e)
                return False
            except Exception as e:
                logger.exception("AIQueue: Unexpected error in put(req_id=%s): %s", req_id, e)
                return False
        
        else: # memory
            if req_id in self._local_seen:
                return False
            self._local_seen.add(req_id)
            await self._local_queue.put(req_id)
            return True

    async def get(self) -> Optional[int]:
        if self._mode == "unknown":
            await self.connect()

        while not self._closed:
            if self._mode == "redis":
                try:
                    res = await self._redis.blpop(self._queue_key, timeout=1)
                    if res:
                        _, req_id_str = res
                        req_id = int(req_id_str)
                        await self._redis.sadd(self._inflight_key, str(req_id))
                        return req_id
                except Exception as e:
                    logger.error(f"AIQueue: Redis get error: {e}")
                    await asyncio.sleep(1) # Backoff
            else:
                # memory
                try:
                    # wait for 1 sec then loop to check Closed
                    req_id = await asyncio.wait_for(self._local_queue.get(), timeout=1)
                    self._local_inflight.add(req_id)
                    return req_id
                except asyncio.TimeoutError:
                    pass

            await asyncio.sleep(0.1)
            
        return None

    async def ack(self, req_id: int) -> None:
        if self._mode == "redis" and self._redis:
            try:
                async with self._redis.pipeline() as pipe:
                    pipe.srem(self._inflight_key, str(req_id))
                    pipe.srem(self._seen_key, str(req_id))
                    await pipe.execute()
            except Exception as e:
                logger.warning("AIQueue: Failed to ack request %s: %s", req_id, e)
        elif self._mode == "memory":
            self._local_inflight.discard(req_id)
            self._local_seen.discard(req_id)
            # Memory queue task_done logic if needed
            # self._local_queue.task_done()

    async def nack(self, req_id: int, *, requeue: bool = True) -> None:
        if self._mode == "redis" and self._redis:
            try:
                async with self._redis.pipeline() as pipe:
                    pipe.srem(self._inflight_key, str(req_id))
                    if not requeue:
                        pipe.srem(self._seen_key, str(req_id))
                    await pipe.execute()
                if requeue:
                    await self._redis.rpush(self._queue_key, str(req_id))
            except Exception as e:
                logger.warning("AIQueue: Failed to nack request %s (requeue=%s): %s", req_id, requeue, e)
        elif self._mode == "memory":
            self._local_inflight.discard(req_id)
            if requeue:
                # Don't remove from seen, just put back
                await self._local_queue.put(req_id)
            else:
                self._local_seen.discard(req_id)

    def is_closed(self) -> bool:
        return self._closed

    async def stats(self) -> Dict[str, int]:
        if self._mode == "redis" and self._redis:
            return {
                "mode": "redis",
                "queued": await self._redis.llen(self._queue_key),
                "seen_total": await self._redis.scard(self._seen_key),
                "inflight": await self._redis.scard(self._inflight_key),
            }
        elif self._mode == "memory":
            return {
                "mode": "memory",
                "queued": self._local_queue.qsize() if self._local_queue else 0,
                "seen_total": len(self._local_seen),
                "inflight": len(self._local_inflight),
            }
        return {"mode": "unknown"}

    async def close(self) -> None:
        self._closed = True

    async def stop(self) -> None:
        await self.close()


# Global singleton
AI_QUEUE = AIQueue()
