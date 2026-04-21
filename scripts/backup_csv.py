"""Export the Transaksi sheet to ./backups/transaksi_YYYYMMDD.csv.

Usage: python -m scripts.backup_csv
"""
import asyncio
import csv
from pathlib import Path
from app.config.settings import PROJECT_ROOT
from app.sheets.client import get_worksheet
from app.utils.logger import setup_logging, get_logger
from app.utils.time import now_jkt


async def main():
    setup_logging()
    log = get_logger("backup_csv")

    def _fetch():
        ws = get_worksheet()
        return ws.get_all_values()

    rows = await asyncio.to_thread(_fetch)
    if not rows:
        log.warning("backup.empty_sheet")
        return

    out_dir = PROJECT_ROOT / "backups"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"transaksi_{now_jkt().strftime('%Y%m%d')}.csv"

    with out_file.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)

    log.info("backup.written", extra={"file": str(out_file), "rows": len(rows)})
    print(f"OK: {out_file} ({len(rows)} rows)")


if __name__ == "__main__":
    asyncio.run(main())
