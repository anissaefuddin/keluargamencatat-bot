from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from app.sheets.analytics import summary_week, summary_month, summary_category
from app.utils.logger import get_logger

log = get_logger(__name__)

router = Router(name="analytics")


@router.message(Command("minggu"))
async def cmd_minggu(message: Message) -> None:
    try:
        text = await summary_week()
        await message.answer(text)
    except Exception:
        log.exception("analytics.week_failed")
        await message.answer("❗ Gagal ambil data, coba lagi ya.")


@router.message(Command("bulan"))
async def cmd_bulan(message: Message) -> None:
    try:
        text = await summary_month()
        await message.answer(text)
    except Exception:
        log.exception("analytics.month_failed")
        await message.answer("❗ Gagal ambil data, coba lagi ya.")


@router.message(Command("laporan"))
async def cmd_laporan(message: Message, command: CommandObject) -> None:
    """/laporan [kategori] — last 30 days for a category."""
    if not command.args:
        await message.answer("Contoh: <code>/laporan makanan</code>")
        return
    try:
        text = await summary_category(command.args.strip())
        await message.answer(text)
    except Exception:
        log.exception("analytics.category_failed")
        await message.answer("❗ Gagal ambil data, coba lagi ya.")
