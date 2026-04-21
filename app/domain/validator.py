from app.config.categories import CATEGORY_SET, DEFAULT_CATEGORY
from app.domain.models import TxnDraft

MAX_NOMINAL = 1_000_000_000


class ValidationError(ValueError):
    pass


def validate_and_coerce(draft: TxnDraft) -> TxnDraft:
    if draft.nominal is None or draft.nominal <= 0:
        raise ValidationError("nominal harus > 0")
    if draft.nominal >= MAX_NOMINAL:
        raise ValidationError("nominal tidak wajar (>= 1 miliar)")
    if draft.tipe_transaksi not in ("pemasukan", "pengeluaran"):
        raise ValidationError(f"tipe_transaksi tidak dikenal: {draft.tipe_transaksi}")
    if draft.kategori not in CATEGORY_SET:
        draft.kategori = DEFAULT_CATEGORY
    if draft.keterangan is None:
        draft.keterangan = ""
    if not isinstance(draft.confidence, (int, float)):
        draft.confidence = 0.0
    draft.confidence = max(0.0, min(1.0, float(draft.confidence)))
    return draft
