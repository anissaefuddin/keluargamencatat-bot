import asyncio
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from gspread.exceptions import APIError
from app.domain.models import TxnRow
from app.sheets.client import get_worksheet
from app.utils.logger import get_logger

log = get_logger(__name__)

_RETRY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(APIError),
    reraise=True,
)


def _append_sync(row: TxnRow) -> int:
    ws = get_worksheet()
    ws.append_row(row.as_list(), value_input_option="USER_ENTERED")
    # row index = all existing rows
    return len(ws.get_all_values())


def _get_last_n_sync(n: int) -> list[dict[str, Any]]:
    ws = get_worksheet()
    all_rows = ws.get_all_records()
    return all_rows[-n:] if all_rows else []


def _update_row_sync(row_index: int, field_to_col: dict[str, int], fields: dict) -> None:
    ws = get_worksheet()
    updates = []
    for fname, value in fields.items():
        if fname in field_to_col:
            col = field_to_col[fname]
            updates.append({"range": ws.cell(row_index, col).address, "values": [[value]]})
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")


# column map matching TxnRow.headers()
_FIELD_TO_COL = {
    "id_transaksi": 1,
    "tanggal": 2,
    "tipe_transaksi": 3,
    "kategori": 4,
    "nominal": 5,
    "keterangan": 6,
    "pengguna": 7,
}


@retry(**_RETRY)
def _append_with_retry(row: TxnRow) -> int:
    return _append_sync(row)


@retry(**_RETRY)
def _get_last_n_with_retry(n: int) -> list[dict[str, Any]]:
    return _get_last_n_sync(n)


@retry(**_RETRY)
def _update_row_with_retry(row_index: int, fields: dict) -> None:
    _update_row_sync(row_index, _FIELD_TO_COL, fields)


async def append(row: TxnRow) -> int:
    log.info("sheets.append", extra={"id": row.id_transaksi, "nominal": row.nominal})
    return await asyncio.to_thread(_append_with_retry, row)


async def get_last_n(n: int = 5) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_get_last_n_with_retry, n)


async def update_row(row_index: int, **fields) -> None:
    log.info("sheets.update_row", extra={"row": row_index, "fields": list(fields.keys())})
    await asyncio.to_thread(_update_row_with_retry, row_index, fields)


async def ensure_header() -> None:
    def _sync():
        ws = get_worksheet()
        vals = ws.get_all_values()
        if not vals or not vals[0] or vals[0][0] != "id_transaksi":
            ws.update("A1:G1", [TxnRow.headers()])
            return True
        return False
    was_created = await asyncio.to_thread(_sync)
    log.info("sheets.ensure_header", extra={"header_created": was_created})
