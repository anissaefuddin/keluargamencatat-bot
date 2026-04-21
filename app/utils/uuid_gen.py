import secrets
from app.utils.time import now_jkt


def new_txn_id() -> str:
    """trx-YYYYMMDD-<6 hex chars>"""
    return f"trx-{now_jkt().strftime('%Y%m%d')}-{secrets.token_hex(3)}"
