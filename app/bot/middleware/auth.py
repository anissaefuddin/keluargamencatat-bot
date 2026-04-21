from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from app.config.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user is None:
            return None
        if user.id not in settings.allowed_user_ids:
            log.info("auth.rejected", extra={"user_id": user.id, "username": user.username})
            return None
        return await handler(event, data)
