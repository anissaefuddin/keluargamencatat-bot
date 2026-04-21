import gspread
from functools import lru_cache
from app.config.settings import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@lru_cache(maxsize=1)
def get_client() -> gspread.Client:
    return gspread.service_account(
        filename=str(settings.creds_abs_path()),
        scopes=SCOPES,
    )


@lru_cache(maxsize=1)
def get_worksheet() -> gspread.Worksheet:
    gc = get_client()
    sh = gc.open_by_key(settings.sheet_id)
    try:
        return sh.worksheet(settings.sheet_tab_name)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=settings.sheet_tab_name, rows=1000, cols=10)
