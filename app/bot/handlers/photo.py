from io import BytesIO
from aiogram import Router, F
from aiogram.types import Message
from app.ai.image_extractor import extract_from_image
from app.ai.text_extractor import categorize_description
from app.config.settings import settings
from app.domain.models import TxnRow
from app.domain.validator import validate_and_coerce, ValidationError
from app.sheets import service as sheets
from app.sheets.dedup import is_duplicate
from app.state import pending_store, last_txn_store, nominal_await_store
from app.bot.keyboards import confirm_kb, dup_kb
from app.utils.time import iso_now_jkt
from app.utils.uuid_gen import new_txn_id
from app.utils.logger import get_logger

log = get_logger(__name__)

router = Router(name="photo")


def _format_pengguna(message: Message) -> str:
    u = message.from_user
    if not u:
        return "unknown"
    return f"@{u.username}" if u.username else f"id:{u.id}"


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    # New photo always supersedes any prior "waiting for nominal" state
    nominal_await_store.clear_waiting(message.from_user.id)

    caption = (message.caption or "").strip()
    if caption:
        await message.answer(f"🧾 Lagi baca struknya dengan catatan: <i>{caption}</i>")
    else:
        await message.answer("🧾 Lagi baca struknya... (pertama kali bisa 1-2 menit)")
    await message.chat.do("typing")

    # Largest photo size (best for OCR)
    photo = message.photo[-1]
    buf = BytesIO()
    await message.bot.download(photo, destination=buf)
    image_bytes = buf.getvalue()

    pengguna = _format_pengguna(message)
    draft = await extract_from_image(image_bytes, pengguna=pengguna)

    # OCR failed (no total). If we have a caption, pre-categorize and wait for
    # the user to send just the nominal as a follow-up text message.
    if not draft:
        if caption:
            cat_info = await categorize_description(caption)
            nominal_await_store.set_waiting(message.from_user.id, {
                "kategori": cat_info["kategori"],
                "tipe_transaksi": cat_info["tipe_transaksi"],
                "keterangan": cat_info["keterangan"] or caption,
                "merchant": "",
                "source": "image_caption",
                "pengguna": pengguna,
            })
            await message.answer(
                "🤖 Saya tidak menemukan total dari struknya 😅\n"
                "Tapi saya mendeteksi:\n"
                f"Kategori: <b>{cat_info['kategori']}</b>\n\n"
                "Kirim saja nominalnya ya (contoh: <code>25000</code> atau <code>25rb</code>)\n"
                "Ketik /batal untuk batalkan."
            )
            return
        await message.answer("Struknya kurang jelas 😕 Bisa ketik nominalnya aja?")
        return

    # If a caption was attached, let text categorize override the image's guess.
    # The image almost always yields kategori="lainnya"; caption gives real context.
    if caption:
        cat_info = await categorize_description(caption)
        draft.kategori = cat_info["kategori"]
        draft.tipe_transaksi = cat_info["tipe_transaksi"]
        # Prefer caption text for keterangan; keep merchant info if we had it
        merchant_hint = draft.keterangan.replace("struk: ", "").strip() if draft.keterangan.startswith("struk:") else ""
        if merchant_hint and merchant_hint.lower() not in caption.lower():
            draft.keterangan = f"{caption} ({merchant_hint})"[:200]
        else:
            draft.keterangan = caption[:200]
        # Caption + image agreement raises confidence above the confirm threshold
        draft.confidence = max(draft.confidence, 0.85)

    try:
        draft = validate_and_coerce(draft)
    except ValidationError:
        await message.answer("Nominal di struk belum kebaca, bisa ketik manual ya.")
        return

    # If caption gave us both high-confidence category AND the image gave the nominal,
    # we can auto-save (still one confirmation for photo safety? — keep the keyboard
    # so the user can correct OCR misreads).
    summary_line = (
        f"🧾 Struk: <b>Rp{draft.nominal:,}</b>".replace(",", ".") +
        f"\nKategori: <b>{draft.kategori}</b>" +
        (f"\nKeterangan: {draft.keterangan}" if draft.keterangan else "")
    )

    # If caption set everything and confidence is high, still confirm (OCR errors are common),
    # but mention dedup up front.
    if draft.confidence >= settings.confidence_threshold and caption:
        # Dup check
        recent = await sheets.get_last_n(5)
        if is_duplicate(draft, recent):
            sent = await message.answer(
                f"{summary_line}\n\n⚠️ Sepertinya duplikat. Tetap simpan?",
                reply_markup=dup_kb(),
            )
            pending_store.put(message.from_user.id, sent.message_id, draft)
            return

    sent = await message.answer(
        summary_line + "\n\nBenar?",
        reply_markup=confirm_kb(),
    )
    pending_store.put(message.from_user.id, sent.message_id, draft)
