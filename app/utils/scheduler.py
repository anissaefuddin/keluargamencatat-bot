"""Minimal in-bot scheduler: runs a coroutine once per day at a target time (Asia/Jakarta)."""
import asyncio
from datetime import datetime, timedelta
from typing import Awaitable, Callable
from app.utils.time import now_jkt
from app.utils.logger import get_logger

log = get_logger(__name__)


def _seconds_until(hour: int, minute: int) -> float:
    now = now_jkt()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def run_daily(coro_factory: Callable[[], Awaitable[None]], hour: int, minute: int, name: str) -> None:
    while True:
        wait = _seconds_until(hour, minute)
        log.info("scheduler.sleeping", extra={"task": name, "seconds": int(wait)})
        await asyncio.sleep(wait)
        try:
            await coro_factory()
            log.info("scheduler.ran", extra={"task": name})
        except Exception:
            log.exception(f"scheduler.{name}_failed")
        # small buffer so we don't re-fire on the same minute
        await asyncio.sleep(61)
