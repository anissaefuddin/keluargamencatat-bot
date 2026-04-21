"""Handles the fallback flow where OCR couldn't read a nominal but we have
category context from the caption — the bot asks the user to reply with just
the number, and this router captures that reply.
"""
from aiogram import Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message
from app.domain.models import TxnRow
from app.domain.normalizer import parse_nominal
from app.sheets import service as sheets
from app.state import nominal_await_store, last_txn_store
from app.utils.time import iso_now_jkt
from app.utils.uuid_gen import new_txn_id
from app.utils.logger import get_logger

log = get_logger(__name__)

router = Router(name="nominal_await")


class _WaitingFilter(BaseFilter):
    """Pass only when the user is currently waiting for a nominal reply."""

    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return nominal_await_store.is_waiting(message.from_user.id)


# /batal works regardless of state — it just clears if there is one.
@router.message(Command("batal"))
async def cmd_batal(message: Message) -> None:
    was_waiting = nominal_await_store.clear_waiting(message.from_user.id)
    if was_waiting:
        await message.answer("❌ Input dibatalkan")
    else:
        await message.answer("Tidak ada yang perlu dibatalkan.")


# Only plain text (not commands, not photos) when the user is in waiting state.
# Registered BEFORE the generic text handler so it runs first.
@router.message(_WaitingFilter(), F.text & ~F.text.startswith("/"))
async def handle_nominal_reply(message: Message) -> None:
    user_id = message.from_user.id
    partial = nominal_await_store.peek_waiting(user_id)
    if not partial:
        # Expired between filter check and body (edge case). Ignore.
        return

    nominal = parse_nominal(message.text or "")
    if not nominal or nominal <= 0:
        await message.answer(
            "Belum kebaca angkanya 🤔 Kirim nominalnya aja, misal:\n"
            "<code>25000</code> atau <code>25rb</code>\n"
            "Atau ketik /batal untuk batalkan."
        )
        return

    # Consume the partial
    partial = nominal_await_store.pop_waiting(user_id)
    assert partial is not None

    merchant = partial.get("merchant", "")
    keterangan = partial.get("keterangan") or ""
    if merchant and merchant.lower() not in keterangan.lower():
        keterangan = f"{keterangan} ({merchant})" if keterangan else merchant
    keterangan = keterangan[:200]

    # Sanity bound (e.g., guard against someone typing "1000000000" by mistake).
    if nominal >= 1_000_000_000:
        await message.answer("Nominal terlalu besar, mohon periksa lagi.")
        nominal_await_store.set_waiting(user_id, partial)
        return

    row = TxnRow(
        id_transaksi=new_txn_id(),
        tanggal=iso_now_jkt(),
        tipe_transaksi=partial.get("tipe_transaksi", "pengeluaran"),
        kategori=partial.get("kategori", "lainnya"),
        nominal=nominal,
        keterangan=keterangan,
        pengguna=partial.get("pengguna", ""),
    )

    try:
        row_index = await sheets.append(row)
        last_txn_store.set_last(user_id, row_index)
        await message.answer(
            f"✅ Tercatat:\nRp{nominal:,} — {row.kategori}".replace(",", ".")
        )
        log.info("nominal_await.saved", extra={"user": user_id, "nominal": nominal, "kat": row.kategori})
    except Exception:
        log.exception("nominal_await.sheets_append_failed")
        # Put the partial back so the user can retry the nominal
        nominal_await_store.set_waiting(user_id, partial)
        await message.answer("❗ Gagal simpan, coba kirim nominalnya lagi ya.")
