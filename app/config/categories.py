ALLOWED_CATEGORIES: list[str] = [
    "makanan",
    "transport",
    "belanja",
    "tagihan",
    "hiburan",
    "kesehatan",
    "pendidikan",
    "gaji",
    "lainnya",
]

CATEGORY_SET: set[str] = set(ALLOWED_CATEGORIES)
DEFAULT_CATEGORY = "lainnya"
