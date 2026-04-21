from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.domain.models import TxnRow
from app.sheets import service as sheets
from app.state import pending_store, last_txn_store
from app.bot.keyboards import category_kb
from app.utils.time import iso_now_jkt
from app.utils.uuid_gen import new_txn_id
from app.utils.logger import get_logger

log = get_logger(__name__)

router = Router(name="confirm")


async def _persist(cq: CallbackQuery, draft) -> None:
    row = TxnRow(
        id_transaksi=new_txn_id(),
        tanggal=iso_now_jkt(),
        tipe_transaksi=draft.tipe_transaksi,
        kategori=draft.kategori,
        nominal=draft.nominal,
        keterangan=draft.keterangan,
        pengguna=draft.pengguna,
    )
    try:
        row_index = await sheets.append(row)
        last_txn_store.set_last(cq.from_user.id, row_index)
        await cq.message.edit_text(
            f"✅ Tercatat: Rp{draft.nominal:,} — {draft.kategori}".replace(",", ".")
        )
    except Exception:
        log.exception("confirm.append_failed")
        await cq.message.edit_text("❗ Gagal simpan, coba lagi ya.")


@router.callback_query(F.data == "confirm:yes")
async def confirm_yes(cq: CallbackQuery) -> None:
    draft = pending_store.pop(cq.from_user.id, cq.message.message_id)
    if not draft:
        await cq.answer("Sudah kadaluarsa", show_alert=False)
        return
    await cq.answer()
    await _persist(cq, draft)


@router.callback_query(F.data == "confirm:no")
async def confirm_no(cq: CallbackQuery) -> None:
    pending_store.pop(cq.from_user.id, cq.message.message_id)
    await cq.answer("Dibatalkan")
    await cq.message.edit_text("❌ Batal dicatat")


@router.callback_query(F.data == "confirm:edit_cat")
async def confirm_edit_cat(cq: CallbackQuery) -> None:
    draft = pending_store.peek(cq.from_user.id, cq.message.message_id)
    if not draft:
        await cq.answer("Sudah kadaluarsa", show_alert=False)
        return
    await cq.answer()
    await cq.message.edit_text(
        f"Pilih kategori untuk Rp{draft.nominal:,}:".replace(",", "."),
        reply_markup=category_kb(),
    )


@router.callback_query(F.data.startswith("set_cat:"))
async def set_category(cq: CallbackQuery) -> None:
    draft = pending_store.pop(cq.from_user.id, cq.message.message_id)
    if not draft:
        await cq.answer("Sudah kadaluarsa", show_alert=False)
        return
    new_cat = cq.data.split(":", 1)[1]
    draft.kategori = new_cat
    await cq.answer(f"Kategori: {new_cat}")
    await _persist(cq, draft)


@router.callback_query(F.data == "dup:save")
async def dup_save(cq: CallbackQuery) -> None:
    draft = pending_store.pop(cq.from_user.id, cq.message.message_id)
    if not draft:
        await cq.answer("Sudah kadaluarsa", show_alert=False)
        return
    await cq.answer()
    await _persist(cq, draft)


@router.callback_query(F.data == "dup:cancel")
async def dup_cancel(cq: CallbackQuery) -> None:
    pending_store.pop(cq.from_user.id, cq.message.message_id)
    await cq.answer("Batal")
    await cq.message.edit_text("❌ Batal dicatat")
