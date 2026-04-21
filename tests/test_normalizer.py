import pytest
from app.domain.normalizer import parse_nominal, normalize_category


@pytest.mark.parametrize("text,expected", [
    ("50rb", 50_000),
    ("50 ribu", 50_000),
    ("50k", 50_000),
    ("1jt", 1_000_000),
    ("1.5jt", 1_500_000),
    ("1,5 juta", 1_500_000),
    ("makan 50rb", 50_000),
    ("beli bensin 100rb transport", 100_000),
    ("150000", 150_000),
    ("Rp 150.000", 150_000),
    ("rp150000", 150_000),
    ("gaji 5 juta", 5_000_000),
    ("kopi 20rb di warung", 20_000),
    ("bayar listrik 350rb", 350_000),
])
def test_parse_nominal_valid(text, expected):
    assert parse_nominal(text) == expected


@pytest.mark.parametrize("text", [
    "hello world",
    "bayar listrik",
    "",
    "tanpa angka sama sekali",
])
def test_parse_nominal_none(text):
    assert parse_nominal(text) is None


@pytest.mark.parametrize("raw,expected", [
    ("makanan", "makanan"),
    ("Makanan", "makanan"),
    ("MAKANAN", "makanan"),
    ("transport", "transport"),
    ("transpor", "transport"),
    ("makan", "makanan"),
    ("unknown_xyz", "lainnya"),
    ("", "lainnya"),
    (None, "lainnya"),
])
def test_normalize_category(raw, expected):
    assert normalize_category(raw) == expected
