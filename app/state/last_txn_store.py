import json
from pathlib import Path
from app.config.settings import PROJECT_ROOT

_STORE_PATH = PROJECT_ROOT / "data" / "last_txn.json"


def _load() -> dict[str, int]:
    if not _STORE_PATH.exists():
        return {}
    try:
        with _STORE_PATH.open() as f:
            raw = json.load(f)
        return {str(k): int(v) for k, v in raw.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, int]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f)
    tmp.replace(_STORE_PATH)


_cache: dict[str, int] = _load()


def set_last(user_id: int, row_index: int) -> None:
    _cache[str(user_id)] = row_index
    _save(_cache)


def get_last(user_id: int) -> int | None:
    return _cache.get(str(user_id))
