import re
from app.domain.models import TxnDraft
from app.domain.normalizer import parse_nominal, normalize_category

_INCOME_KEYWORDS = re.compile(
    r"\b(gaji|bonus|thr|transfer masuk|pemasukan|dapat|terima)\b", re.IGNORECASE,
)

_CATEGORY_HINTS = [
    (re.compile(r"\b(makan|makanan|kopi|sarapan|dinner|lunch|warung)\b", re.I), "makanan"),
    (re.compile(r"\b(bensin|grab|gojek|ojek|parkir|bus|kereta|taksi|tol)\b", re.I), "transport"),
    (re.compile(r"\b(belanja|baju|sepatu|mall|toko|groceries)\b", re.I), "belanja"),
    (re.compile(r"\b(listrik|air|internet|wifi|pulsa|pajak|iuran)\b", re.I), "tagihan"),
    (re.compile(r"\b(nonton|bioskop|game|netflix|spotify|hiburan)\b", re.I), "hiburan"),
    (re.compile(r"\b(obat|dokter|rumah sakit|vitamin|kesehatan)\b", re.I), "kesehatan"),
    (re.compile(r"\b(sekolah|kursus|buku|les|pendidikan)\b", re.I), "pendidikan"),
    (re.compile(r"\b(gaji|bonus|thr)\b", re.I), "gaji"),
]


def extract_by_regex(text: str) -> TxnDraft | None:
    nominal = parse_nominal(text)
    if not nominal:
        return None

    tipe = "pemasukan" if _INCOME_KEYWORDS.search(text) else "pengeluaran"
    kategori = "lainnya"
    for pat, cat in _CATEGORY_HINTS:
        if pat.search(text):
            kategori = cat
            break
    kategori = normalize_category(kategori)

    return TxnDraft(
        nominal=nominal,
        tipe_transaksi=tipe,
        kategori=kategori,
        keterangan=text.strip()[:120],
        confidence=0.55,
        raw_input=text,
        source="text",
    )
