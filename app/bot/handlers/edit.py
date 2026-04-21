from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from app.domain.normalizer import parse_nominal, normalize_category
from app.sheets import service as sheets
from app.state import last_txn_store
from app.utils.logger import get_logger

log = get_logger(__name__)

router = Router(name="edit")


@router.message(Command("ubah"))
async def cmd_ubah(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Contoh: <code>/ubah 75000</code> atau <code>/ubah 75rb</code>")
        return
    nominal = parse_nominal(command.args)
    if not nominal:
        await message.answer("Nominalnya belum kebaca, contoh: <code>/ubah 75rb</code>")
        return
    row_idx = last_txn_store.get_last(message.from_user.id)
    if not row_idx:
        await message.answer("Belum ada transaksi terakhir di sesi ini.")
        return
    try:
        await sheets.update_row(row_idx, nominal=nominal)
        await message.answer(f"✏️ Nominal diubah jadi Rp{nominal:,}".replace(",", "."))
    except Exception:
        log.exception("edit.ubah_failed")
        await message.answer("❗ Gagal update, coba lagi ya.")


@router.message(Command("kategori"))
async def cmd_kategori(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer("Contoh: <code>/kategori transport</code>")
        return
    cat = normalize_category(command.args)
    row_idx = last_txn_store.get_last(message.from_user.id)
    if not row_idx:
        await message.answer("Belum ada transaksi terakhir.")
        return
    try:
        await sheets.update_row(row_idx, kategori=cat)
        await message.answer(f"✏️ Kategori diubah jadi <b>{cat}</b>")
    except Exception:
        log.exception("edit.kategori_failed")
        await message.answer("❗ Gagal update, coba lagi ya.")
