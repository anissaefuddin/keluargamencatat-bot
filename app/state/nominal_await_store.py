"""User-scoped 'waiting for nominal' state, set when OCR couldn't read the total
but the caption gave us a category. TTL 5 minutes, lazy-purge on access.

Shape of the stored partial:
    {
        "kategori": str,
        "tipe_transaksi": str,
        "keterangan": str,
        "merchant": str,           # from image OCR, may be empty
        "source": str,             # "image_caption"
        "pengguna": str,
    }
"""
import time
from typing import TypedDict

_TTL_SECONDS = 300


class AwaitPartial(TypedDict, total=False):
    kategori: str
    tipe_transaksi: str
    keterangan: str
    merchant: str
    source: str
    pengguna: str


_store: dict[int, tuple[float, AwaitPartial]] = {}


def _purge() -> None:
    now = time.time()
    expired = [uid for uid, (ts, _) in _store.items() if now - ts > _TTL_SECONDS]
    for uid in expired:
        _store.pop(uid, None)


def set_waiting(user_id: int, partial: AwaitPartial) -> None:
    _purge()
    _store[user_id] = (time.time(), partial)


def peek_waiting(user_id: int) -> AwaitPartial | None:
    _purge()
    item = _store.get(user_id)
    return item[1] if item else None


def pop_waiting(user_id: int) -> AwaitPartial | None:
    _purge()
    item = _store.pop(user_id, None)
    return item[1] if item else None


def clear_waiting(user_id: int) -> bool:
    return _store.pop(user_id, None) is not None


def is_waiting(user_id: int) -> bool:
    _purge()
    return user_id in _store
