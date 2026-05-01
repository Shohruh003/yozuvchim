import asyncio
import os
import sys
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Set

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy import select, update

from bot.config import SETTINGS, logger
from bot.database import init_db, AsyncSessionLocal, Request, engine, DB
from bot.handlers import router
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.menu_middleware import MenuMiddleware
from bot.queue_manager import AI_QUEUE
from bot.worker import worker
from bot.services.ai_service import ai_service


# Redis handles deduplication now, no need for process-level _SEEN_QUEUE_IDS


async def load_pending_requests_into_queue() -> int:
    """
    Startup recovery:
    - Restores 'queued' or 'locked' (timed out) requests into the queue on startup.
    - Moves 'processing' requests back to 'queued' if they timed out.
    """
    count = 0
    async with AsyncSessionLocal() as session:
        # On fresh startup, NOTHING can be actually processing — reset ALL
        await session.execute(
            update(Request)
            .where(Request.status == "processing")
            .values(status="queued", locked_by=None, locked_at=None)
        )
        
        # 2. Get all 'queued' requests
        res = await session.execute(
            select(Request.id).where(Request.status == "queued").order_by(Request.created_at.asc())
        )
        pids = res.scalars().all()
        for rid in pids:
            if await AI_QUEUE.put(rid):
                count += 1
        
        await session.commit()
    return count


def _task_exception_logger(task: asyncio.Task) -> None:
    """
    Logs unhandled exceptions inside background tasks (worker).
    """
    with suppress(asyncio.CancelledError):
        exc = task.exception()
        if exc:
            logger.exception("Background task crashed!", exc_info=exc)


async def run_watchdog(bot: Bot) -> None:
    """
    Periodic background task:
    1. Re-queues requests stuck in 'processing' for too long (> 30 mins).
    2. Cleans up old results (> 1 day) to save database and disk space.
    3. Deletes old request rows (> 30 days) to keep DB small.
    """
    logger.info("Watchdog task started (interval: 15m).")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.utcnow()
                
                # 1. Recover stuck requests (Same 30m threshold as startup)
                recovery_threshold = now - timedelta(minutes=30)
                stuck_res = await session.execute(
                    update(Request)
                    .where(Request.status == "processing")
                    .where(Request.locked_at < recovery_threshold)
                    .values(status="queued", locked_by=None, locked_at=None)
                )
                if stuck_res.rowcount:
                    logger.warning(f"Watchdog: Recovered {stuck_res.rowcount} stuck request(s).")
                
                # 2. Cleanup old results (1 day)
                one_day_ago = now - timedelta(days=1)

                old_reqs = await session.execute(
                    select(Request)
                    .where(Request.status == "done")
                    .where(Request.created_at < one_day_ago)
                    .where(Request.is_deleted == False)
                )
                old_list = old_reqs.scalars().all()
                for old_req in old_list:
                    if old_req.result_path:
                        from pathlib import Path
                        p = Path(old_req.result_path)
                        if p.exists():
                            p.unlink()
                            logger.info(f"Watchdog: Deleted file {p}")
                    old_req.result_text = None
                    old_req.meta_json = {}
                    old_req.is_deleted = True
                if old_list:
                    logger.info(f"Watchdog: Cleared {len(old_list)} old request(s).")

                # 3. Delete old request rows (30 days) to keep DB small
                thirty_days_ago = now - timedelta(days=30)
                from sqlalchemy import delete
                del_result = await session.execute(
                    delete(Request)
                    .where(Request.created_at < thirty_days_ago)
                    .where(Request.status.in_(["done", "error"]))
                )
                if del_result.rowcount:
                    logger.info(f"Watchdog: Deleted {del_result.rowcount} old request row(s) (>30 days).")
                
                await session.commit()
        except Exception as e:
            logger.error(f"Watchdog Error: {e}", exc_info=True)
            await asyncio.sleep(60)
            continue
            
        await asyncio.sleep(900) # Every 15 minutes


async def main() -> None:
    # --- Singleton Process Lock ---
    pid_file = "academic_bot.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            
            import psutil
            if psutil.pid_exists(old_pid):
                # Extra check: is it really our python process?
                proc = psutil.Process(old_pid)
                if "python" in proc.name().lower():
                    logger.error(f"Bot allaqachon ishlayapti (PID: {old_pid}). Yangi nusxa ishga tushirilmadi.")
                    return
        except Exception as e:
            logger.warning(f"PID check failed: {e}")
            pass
            
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    await init_db()

    # Load admin cache (env + DB admins)
    async with AsyncSessionLocal() as session:
        admin_ids = await DB.load_admin_cache(session)
        logger.info(f"Admin cache loaded: {len(admin_ids)} admin(s).")

    bot = Bot(token=SETTINGS.bot_token)
    
    # FSM Storage — use MemoryStorage by default; opt-in to Redis with USE_REDIS_FSM=1
    use_redis_fsm = os.getenv("USE_REDIS_FSM", "0") == "1"
    storage = None
    if use_redis_fsm:
        try:
            from redis.asyncio import Redis
            redis_client = Redis.from_url(SETTINGS.redis_url)
            await redis_client.ping()
            storage = RedisStorage(redis=redis_client)
            logger.info("FSM Storage: Using Redis.")
        except Exception as e:
            logger.warning(f"FSM Storage: Redis failed ({e}). Falling back to MemoryStorage.")
    if storage is None:
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()
        logger.info("FSM Storage: MemoryStorage.")
        
    dp = Dispatcher(storage=storage)

    # Middlewares / Routers
    dp.message.middleware(MenuMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
    dp.include_router(router)

    # Connect to Queue (Redis)
    await AI_QUEUE.connect()

    # Startup restore
    try:
        loaded = await load_pending_requests_into_queue()
        logger.info(f"Startup recovery: loaded {loaded} pending request(s) into AI queue.")
    except Exception:
        logger.exception("Startup recovery failed (pending requests restore).")

    # Start worker
    worker_task = asyncio.create_task(worker(bot), name="ai_worker")
    worker_task.add_done_callback(_task_exception_logger)

    # Start watchdog
    watchdog_task = asyncio.create_task(run_watchdog(bot), name="watchdog")
    watchdog_task.add_done_callback(_task_exception_logger)

    skip_updates = getattr(SETTINGS, "skip_updates", True)

    try:
        logger.info("Bot starting...")
        me = await bot.get_me()
        logger.info(f"Bot @{me.username} connected. Polling started. skip_updates={skip_updates}")

        await dp.start_polling(bot, skip_updates=skip_updates)

    finally:
        logger.warning("Shutting down...")

        # close AI service session
        with suppress(Exception):
            logger.info("Closing AI service...")
            await ai_service.close()

        # stop worker
        worker_task.cancel()
        watchdog_task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(worker_task, watchdog_task)

        # close storage (aiogram3)
        with suppress(Exception):
            await dp.storage.close()

        # close bot session
        with suppress(Exception):
            await bot.session.close()

        # close queue (Redis)
        with suppress(Exception):
            await AI_QUEUE.disconnect()

        # dispose DB engine
        with suppress(Exception):
            await engine.dispose()
            logger.info("DB engine disposed.")

        # remove pid file
        with suppress(Exception):
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.info("PID file removed.")
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")

