import asyncio
import tempfile
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message
from app.ai.whisper_client import transcribe
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

router = Router(name="voice")


def _format_pengguna(message: Message) -> str:
    u = message.from_user
    if not u:
        return "unknown"
    return f"@{u.username}" if u.username else f"id:{u.id}"


async def _convert_to_wav(src: Path, dst: Path) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src), "-ar", "16000", "-ac", "1", str(dst),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        log.warning("voice.ffmpeg_failed", extra={"err": err.decode()[:200]})
        return False
    return True


@router.message(F.voice | F.audio)
async def handle_voice(message: Message) -> None:
    await message.chat.do("typing")

    file = message.voice or message.audio
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.ogg"
        wav = Path(td) / "in.wav"
        await message.bot.download(file, destination=src)

        if not await _convert_to_wav(src, wav):
            await message.answer("Audio-nya gak bisa diproses. Ketik aja ya.")
            return

        text, conf = await transcribe(str(wav))

    if not text:
        await message.answer("Audio kurang jelas, bisa ulangi atau ketik saja?")
        return

    log.info("voice.transcribed", extra={"text": text[:120], "lang_prob": conf})

    pengguna = _format_pengguna(message)
    draft = await extract(text, pengguna=pengguna)
    if draft is None:
        await message.answer(
            f"🎤 Dengar: <i>{text}</i>\n\nTapi belum kebaca nominalnya, bisa ketik ya."
        )
        return

    # Show what we heard + the extracted draft
    if draft.confidence < settings.confidence_threshold:
        sent = await message.answer(
            f"🎤 Dengar: <i>{text}</i>\n\n"
            f"Benar <b>Rp{draft.nominal:,}</b> kategori <b>{draft.kategori}</b>?".replace(",", "."),
            reply_markup=confirm_kb(),
        )
        pending_store.put(message.from_user.id, sent.message_id, draft)
        return

    # Dup check + save
    recent = await sheets.get_last_n(5)
    if is_duplicate(draft, recent):
        sent = await message.answer(
            f"🎤 <i>{text}</i>\n\n⚠️ Duplikat? Tetap simpan?",
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
        await message.answer(
            f"🎤 <i>{text}</i>\n\n✅ Tercatat: Rp{draft.nominal:,} — {draft.kategori}".replace(",", ".")
        )
    except Exception:
        log.exception("voice.sheets_append_failed")
        await message.answer("❗ Gagal simpan ke Sheets, coba lagi ya.")
