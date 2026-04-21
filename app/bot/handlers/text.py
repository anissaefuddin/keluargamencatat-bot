from aiogram import Router, F
from aiogram.types import Message
from app.ai.text_extractor import extract
from app.config.settings import settings
from app.domain.models import TxnRow
from app.sheets import service as sheets
from app.sheets.dedup import is_duplicate
from app.state import pending_store, last_txn_store
from app.bot.keyboards import confirm_kb, dup_kb
from app.utils.time import iso_now_jkt
from app.utils.uuid_gen import new_txn_id
from app.utils.logger import get_logger

log = get_logger(__name__)

_TIPE_LABEL = {"pemasukan": "Pemasukan", "pengeluaran": "Pengeluaran"}


def _format_pengguna(message: Message) -> str:
    u = message.from_user
    if not u:
        return "unknown"
    return f"@{u.username}" if u.username else f"id:{u.id}"


def _format_summary(d) -> str:
    tipe = _TIPE_LABEL.get(d.tipe_transaksi, d.tipe_transaksi)
    return f"✅ Tercatat: {tipe} Rp{d.nominal:,} — {d.kategori}".replace(",", ".")


async def _save_and_reply(message: Message, draft) -> None:
    recent = await sheets.get_last_n(5)
    if is_duplicate(draft, recent):
        pending_store.put(message.from_user.id, message.message_id, draft)
        sent = await message.answer(
            f"⚠️ Sepertinya duplikat (Rp{draft.nominal:,} — {draft.kategori}). Tetap simpan?".replace(",", "."),
            reply_markup=dup_kb(),
        )
        pending_store.put(message.from_user.id, sent.message_id, draft)
        return

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
        last_txn_store.set_last(message.from_user.id, row_index)
        await message.answer(_format_summary(draft))
    except Exception as e:
        log.exception("sheets.append_failed")
        await message.answer("❗ Gagal simpan ke Sheets, akan dicoba ulang otomatis.")


router = Router(name="text")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message) -> None:
    pengguna = _format_pengguna(message)
    draft = await extract(message.text, pengguna=pengguna)
    if draft is None:
        await message.answer(
            "Belum kebaca 🤔 Coba format seperti: <code>makan 50rb</code> atau <code>bensin 100000</code>"
        )
        return

    if draft.confidence < settings.confidence_threshold:
        sent = await message.answer(
            f"Benar <b>Rp{draft.nominal:,}</b> kategori <b>{draft.kategori}</b>?".replace(",", "."),
            reply_markup=confirm_kb(),
        )
        pending_store.put(message.from_user.id, sent.message_id, draft)
        return

    await _save_and_reply(message, draft)
