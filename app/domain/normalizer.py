import re
from difflib import SequenceMatcher
from app.config.categories import ALLOWED_CATEGORIES, DEFAULT_CATEGORY

_NOMINAL_WITH_UNIT = re.compile(
    r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>rb|ribu|k|jt|juta|m|miliar)\b",
    re.IGNORECASE,
)
_NOMINAL_PLAIN = re.compile(r"(?<!\d)(\d{3,})(?!\d)")

_UNIT_MULTIPLIERS = {
    "rb": 1_000,
    "ribu": 1_000,
    "k": 1_000,
    "jt": 1_000_000,
    "juta": 1_000_000,
    "m": 1_000_000_000,
    "miliar": 1_000_000_000,
}


def parse_nominal(text: str) -> int | None:
    """Parse Indonesian money shorthand.

    Examples:
      "50rb", "50 ribu", "50k" -> 50000
      "1.5jt", "1,5 juta"      -> 1500000
      "150000", "Rp 150.000"   -> 150000
    Returns None if nothing parseable.
    """
    if text is None:
        return None
    s = text.strip().lower().replace("rp", "")

    # Treat comma as decimal separator for unit matches ("1,5 juta" -> "1.5 juta")
    s_unit = re.sub(r"(\d),(\d)", r"\1.\2", s)
    m = _NOMINAL_WITH_UNIT.search(s_unit)
    if m:
        num = float(m.group("num"))
        mult = _UNIT_MULTIPLIERS[m.group("unit").lower()]
        return int(num * mult)

    # Strip thousands separators: "150.000"/"150,000" -> "150000"
    s_plain = re.sub(r"[.,](\d{3})(?!\d)", r"\1", s)
    m2 = _NOMINAL_PLAIN.search(s_plain)
    if m2:
        try:
            return int(m2.group(1))
        except ValueError:
            return None
    return None


def normalize_category(raw: str | None) -> str:
    if not raw:
        return DEFAULT_CATEGORY
    r = raw.strip().lower()
    if r in ALLOWED_CATEGORIES:
        return r
    best, best_ratio = DEFAULT_CATEGORY, 0.0
    for cat in ALLOWED_CATEGORIES:
        ratio = SequenceMatcher(None, r, cat).ratio()
        if ratio > best_ratio:
            best, best_ratio = cat, ratio
    return best if best_ratio >= 0.7 else DEFAULT_CATEGORY
