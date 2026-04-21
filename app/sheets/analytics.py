"""Read-only analytics over the Sheets log."""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from app.sheets.client import get_worksheet
from app.utils.time import now_jkt


def _all_rows_sync() -> list[dict[str, Any]]:
    return get_worksheet().get_all_records(value_render_option="UNFORMATTED_VALUE")


async def _all_rows() -> list[dict[str, Any]]:
    return await asyncio.to_thread(_all_rows_sync)


def _parse_ts(row: dict) -> datetime | None:
    raw = str(row.get("tanggal", ""))
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_nominal(row: dict) -> int:
    v = row.get("nominal", 0)
    if isinstance(v, (int, float)):
        return int(v)
    # Fallback for formatted strings like "Rp12,345" (in case UNFORMATTED_VALUE fails)
    try:
        s = str(v).lower().replace("rp", "").replace(",", "").replace(".", "").strip()
        return int(s) if s else 0
    except (ValueError, TypeError):
        return 0


def _filter(rows: list[dict], since: datetime, pengguna: str | None = None) -> list[dict]:
    out = []
    for r in rows:
        ts = _parse_ts(r)
        if ts is None or ts < since:
            continue
        if pengguna and str(r.get("pengguna", "")) != pengguna:
            continue
        out.append(r)
    return out


def _sum_by(rows: list[dict], key: str) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for r in rows:
        if str(r.get("tipe_transaksi", "")) != "pengeluaran":
            continue
        totals[str(r.get(key, "lainnya"))] += _parse_nominal(r)
    return dict(sorted(totals.items(), key=lambda x: -x[1]))


def _fmt_rp(n: int) -> str:
    return f"Rp{n:,}".replace(",", ".")


async def summary_since(since: datetime, title: str, pengguna: str | None = None) -> str:
    rows = _filter(await _all_rows(), since, pengguna)
    if not rows:
        return f"📊 <b>{title}</b>\nBelum ada transaksi."

    expense_rows = [r for r in rows if r.get("tipe_transaksi") == "pengeluaran"]
    income_rows = [r for r in rows if r.get("tipe_transaksi") == "pemasukan"]

    total_expense = sum(_parse_nominal(r) for r in expense_rows)
    total_income = sum(_parse_nominal(r) for r in income_rows)
    by_cat = _sum_by(expense_rows, "kategori")

    lines = [f"📊 <b>{title}</b>"]
    lines.append(f"Transaksi: {len(rows)} ({len(expense_rows)} pengeluaran, {len(income_rows)} pemasukan)")
    if total_income:
        lines.append(f"Pemasukan: <b>{_fmt_rp(total_income)}</b>")
    lines.append(f"Pengeluaran: <b>{_fmt_rp(total_expense)}</b>")
    if by_cat:
        lines.append("\nPer kategori:")
        for cat, amt in by_cat.items():
            lines.append(f"  • {cat}: {_fmt_rp(amt)}")
    return "\n".join(lines)


async def summary_category(kategori: str, days: int = 30) -> str:
    since = now_jkt() - timedelta(days=days)
    rows = _filter(await _all_rows(), since)
    hits = [r for r in rows if str(r.get("kategori", "")).lower() == kategori.lower()]
    if not hits:
        return f"📊 <b>Kategori {kategori}</b> ({days} hari)\nBelum ada transaksi."
    total = sum(_parse_nominal(r) for r in hits)
    lines = [f"📊 <b>Kategori {kategori}</b> ({days} hari)"]
    lines.append(f"Total: <b>{_fmt_rp(total)}</b> ({len(hits)} transaksi)")
    lines.append("")
    for r in hits[-10:]:
        ts = _parse_ts(r)
        date_str = ts.strftime("%d/%m") if ts else "?"
        lines.append(f"  • {date_str} {_fmt_rp(_parse_nominal(r))} — {r.get('keterangan', '')[:40]}")
    return "\n".join(lines)


async def summary_week() -> str:
    now = now_jkt()
    monday = now - timedelta(days=now.weekday())
    since = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return await summary_since(since, "Minggu ini")


async def summary_month() -> str:
    now = now_jkt()
    since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return await summary_since(since, f"Bulan {now.strftime('%B %Y')}")
