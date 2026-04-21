from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")


def now_jkt() -> datetime:
    return datetime.now(JAKARTA_TZ)


def iso_now_jkt() -> str:
    return now_jkt().isoformat()
