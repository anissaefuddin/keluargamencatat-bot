"""Create the header row in the configured Google Sheet if missing."""
import asyncio
from app.sheets.service import ensure_header
from app.utils.logger import setup_logging


async def main():
    setup_logging()
    await ensure_header()
    print("OK: sheet header ensured")


if __name__ == "__main__":
    asyncio.run(main())
