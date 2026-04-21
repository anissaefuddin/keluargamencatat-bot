from io import BytesIO
from aiogram import Router, F
from aiogram.types import Message
from app.ai.image_extractor import extract_from_image
from app.domain.validator import validate_and_coerce, ValidationError
from app.state import pending_store
from app.bot.keyboards import confirm_kb
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
    await message.chat.do("typing")
    # Largest photo size (best for OCR)
    photo = message.photo[-1]
    buf = BytesIO()
    await message.bot.download(photo, destination=buf)
    image_bytes = buf.getvalue()

    draft = await extract_from_image(image_bytes, pengguna=_format_pengguna(message))
    if not draft:
        await message.answer("Struknya kurang jelas 😕 Bisa ketik nominalnya aja?")
        return

    try:
        draft = validate_and_coerce(draft)
    except ValidationError:
        await message.answer("Nominal di struk belum kebaca, bisa ketik manual ya.")
        return

    # Always force confirmation for photos
    sent = await message.answer(
        f"🧾 Struk terbaca: <b>Rp{draft.nominal:,}</b>".replace(",", ".") +
        (f"\nKeterangan: {draft.keterangan}" if draft.keterangan else "") +
        "\n\nBenar? Pilih kategori juga ya.",
        reply_markup=confirm_kb(),
    )
    pending_store.put(message.from_user.id, sent.message_id, draft)
