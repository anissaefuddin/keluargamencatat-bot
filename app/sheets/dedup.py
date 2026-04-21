from datetime import datetime, timedelta
from typing import Any
from app.domain.models import TxnDraft
from app.utils.time import now_jkt


def is_duplicate(
    draft: TxnDraft,
    recent_rows: list[dict[str, Any]],
    window_seconds: int = 60,
) -> bool:
    now = now_jkt()
    for row in recent_rows:
        if str(row.get("pengguna", "")) != draft.pengguna:
            continue
        try:
            row_nominal = int(row.get("nominal", 0))
        except (ValueError, TypeError):
            continue
        if row_nominal != draft.nominal:
            continue
        ts_raw = str(row.get("tanggal", ""))
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue
        if ts.tzinfo is None:
            # best-effort: assume same tz
            ts = ts.replace(tzinfo=now.tzinfo)
        if abs((now - ts).total_seconds()) <= window_seconds:
            return True
    return False
