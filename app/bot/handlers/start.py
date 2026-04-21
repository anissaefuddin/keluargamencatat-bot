from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "kamu"
    await message.answer(
        f"Halo {name}! Kirim pencatatan apa aja, contoh:\n\n"
        "• <code>makan siang 50rb</code>\n"
        "• <code>bensin 100rb</code>\n"
        "• <code>gaji 5 juta</code>\n\n"
        "Perintah:\n"
        "/ubah &lt;nominal&gt; — ubah nominal transaksi terakhir\n"
        "/kategori &lt;nama&gt; — ubah kategori terakhir\n"
        "/help — bantuan"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Kirim teks bebas, misalnya <code>kopi 20rb</code>. "
        "Aku akan catat ke Google Sheets.\n\n"
        "Koreksi:\n"
        "/ubah 75000 — ganti nominal terakhir\n"
        "/kategori transport — ganti kategori terakhir"
    )
