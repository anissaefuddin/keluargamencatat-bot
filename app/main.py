import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.config.settings import settings
from app.bot.middleware.auth import WhitelistMiddleware
from app.bot.handlers import (
    start as h_start,
    text as h_text,
    confirm as h_confirm,
    edit as h_edit,
    analytics as h_analytics,
    photo as h_photo,
    voice as h_voice,
    nominal_await as h_nominal_await,
)
from app.sheets.service import ensure_header
from app.ai.ollama_client import warm_up
from app.utils.logger import setup_logging, get_logger
from app.utils.scheduler import run_daily


async def main() -> None:
    setup_logging()
    log = get_logger("main")

    bot = Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    auth = WhitelistMiddleware()
    dp.message.middleware(auth)
    dp.callback_query.middleware(auth)

    dp.include_router(h_start.router)
    dp.include_router(h_edit.router)
    dp.include_router(h_analytics.router)
    dp.include_router(h_confirm.router)
    dp.include_router(h_photo.router)
    dp.include_router(h_voice.router)
    dp.include_router(h_nominal_await.router)  # MUST be before h_text for the waiting-state filter
    dp.include_router(h_text.router)

    try:
        await ensure_header()
    except Exception as e:
        log.warning(f"ensure_header failed (continuing): {e}")

    asyncio.create_task(warm_up())

    async def _daily_backup():
        from scripts.backup_csv import main as backup_main
        await backup_main()
    asyncio.create_task(run_daily(_daily_backup, hour=2, minute=0, name="csv_backup"))

    log.info("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
