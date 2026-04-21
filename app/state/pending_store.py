import time
from app.domain.models import TxnDraft

_TTL_SECONDS = 300

_store: dict[tuple[int, int], tuple[float, TxnDraft]] = {}


def _purge() -> None:
    now = time.time()
    expired = [k for k, (ts, _) in _store.items() if now - ts > _TTL_SECONDS]
    for k in expired:
        _store.pop(k, None)


def put(user_id: int, msg_id: int, draft: TxnDraft) -> None:
    _purge()
    _store[(user_id, msg_id)] = (time.time(), draft)


def pop(user_id: int, msg_id: int) -> TxnDraft | None:
    _purge()
    item = _store.pop((user_id, msg_id), None)
    if item is None:
        return None
    return item[1]


def peek(user_id: int, msg_id: int) -> TxnDraft | None:
    _purge()
    item = _store.get((user_id, msg_id))
    return item[1] if item else None
