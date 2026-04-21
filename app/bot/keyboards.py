from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.config.categories import ALLOWED_CATEGORIES


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ya", callback_data="confirm:yes"),
            InlineKeyboardButton(text="❌ Tidak", callback_data="confirm:no"),
        ],
        [InlineKeyboardButton(text="✏️ Ubah kategori", callback_data="confirm:edit_cat")],
    ])


def dup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ya, simpan", callback_data="dup:save"),
        InlineKeyboardButton(text="❌ Batal", callback_data="dup:cancel"),
    ]])


def category_kb() -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for i, cat in enumerate(ALLOWED_CATEGORIES, 1):
        row.append(InlineKeyboardButton(text=cat, callback_data=f"set_cat:{cat}"))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
