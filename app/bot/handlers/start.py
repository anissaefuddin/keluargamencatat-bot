from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "kamu"
    await message.answer(
        f"Halo {name}! Kirim pencatatan apa aja:\n\n"
        "💬 <b>Teks</b>: <code>makan siang 50rb</code>\n"
        "🎤 <b>Voice note</b>: rekam bicara pencatatan\n"
        "🧾 <b>Foto struk</b>: kirim foto struk belanja\n\n"
        "<b>Perintah:</b>\n"
        "/minggu — laporan minggu ini\n"
        "/bulan — laporan bulan ini\n"
        "/laporan &lt;kategori&gt; — detail 30 hari\n"
        "/ubah &lt;nominal&gt; — ubah nominal terakhir\n"
        "/kategori &lt;nama&gt; — ubah kategori terakhir\n"
        "/help — bantuan"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Kirim teks, voice, atau foto struk — otomatis dicatat ke Google Sheets.\n\n"
        "<b>Contoh:</b>\n"
        "• <code>kopi 20rb</code>\n"
        "• <code>bensin 100k</code>\n"
        "• <code>gaji 5 juta</code>\n\n"
        "<b>Analitik:</b>\n"
        "/minggu, /bulan — ringkasan\n"
        "/laporan makanan — detail kategori\n\n"
        "<b>Koreksi terakhir:</b>\n"
        "/ubah 75000, /kategori transport"
    )
