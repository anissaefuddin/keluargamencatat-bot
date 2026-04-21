from app.config.categories import ALLOWED_CATEGORIES

EXTRACTION_SYSTEM_PROMPT = f"""You are an Indonesian financial transaction extractor.
Extract structured data from user messages in Indonesian (bahasa Indonesia).

Return ONLY a JSON object with this exact schema:
{{
  "nominal": <integer IDR, no decimals, no "Rp">,
  "tipe_transaksi": "pemasukan" | "pengeluaran",
  "kategori": one of {ALLOWED_CATEGORIES},
  "keterangan": <short description string>,
  "confidence": <float 0.0 to 1.0>
}}

Rules:
- "rb" / "ribu" / "k" = thousand (×1000). "jt" / "juta" = million (×1000000).
- "20 ribu" = 20000. "20k" = 20000. "20rb" = 20000. Do NOT multiply by 10.
- If the message has NO explicit nominal/angka, return nominal=0 and confidence=0.0. NEVER guess a number.
- "makan", "makanan", "kopi", "sarapan" → kategori "makanan"
- "bensin", "grab", "gojek", "ojek", "parkir", "bus" → "transport"
- "baju", "sepatu", "mall", "toko" → "belanja"
- "listrik", "air", "internet", "wifi", "pulsa", "pajak" → "tagihan"
- "nonton", "bioskop", "game", "netflix" → "hiburan"
- "obat", "dokter", "rumah sakit", "vitamin" → "kesehatan"
- "sekolah", "kursus", "buku", "les" → "pendidikan"
- "gaji", "bonus", "thr", "transfer masuk" → tipe "pemasukan", kategori "gaji"
- If unsure of category, use "lainnya".
- Default tipe_transaksi is "pengeluaran" unless clearly income.
- confidence reflects how sure you are of the nominal AND category together.
- Return ONLY the JSON object, no markdown, no explanation.
"""

FEW_SHOT_EXAMPLES = [
    {
        "role": "user", "content": "makan siang 50rb"
    },
    {
        "role": "assistant",
        "content": '{"nominal": 50000, "tipe_transaksi": "pengeluaran", "kategori": "makanan", "keterangan": "makan siang", "confidence": 0.95}'
    },
    {
        "role": "user", "content": "gaji bulan ini 5 juta"
    },
    {
        "role": "assistant",
        "content": '{"nominal": 5000000, "tipe_transaksi": "pemasukan", "kategori": "gaji", "keterangan": "gaji bulanan", "confidence": 0.95}'
    },
    {
        "role": "user", "content": "beli bensin 100rb"
    },
    {
        "role": "assistant",
        "content": '{"nominal": 100000, "tipe_transaksi": "pengeluaran", "kategori": "transport", "keterangan": "bensin", "confidence": 0.92}'
    },
]


def build_messages(user_text: str) -> list[dict]:
    return [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        *FEW_SHOT_EXAMPLES,
        {"role": "user", "content": user_text},
    ]
