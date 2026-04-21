import pytest
from app.domain.models import TxnDraft
from app.domain.validator import validate_and_coerce, ValidationError


def _draft(**kw) -> TxnDraft:
    base = dict(
        nominal=50_000,
        tipe_transaksi="pengeluaran",
        kategori="makanan",
        keterangan="makan siang",
        confidence=0.9,
        raw_input="makan 50rb",
        source="text",
        pengguna="@anis",
    )
    base.update(kw)
    return TxnDraft(**base)


def test_ok():
    d = validate_and_coerce(_draft())
    assert d.nominal == 50_000


def test_zero_nominal_raises():
    with pytest.raises(ValidationError):
        validate_and_coerce(_draft(nominal=0))


def test_huge_nominal_raises():
    with pytest.raises(ValidationError):
        validate_and_coerce(_draft(nominal=2_000_000_000))


def test_bad_tipe_raises():
    with pytest.raises(ValidationError):
        validate_and_coerce(_draft(tipe_transaksi="lol"))


def test_unknown_category_coerced_to_lainnya():
    d = validate_and_coerce(_draft(kategori="unknown_foo"))
    assert d.kategori == "lainnya"


def test_confidence_clamped():
    d = validate_and_coerce(_draft(confidence=2.5))
    assert d.confidence == 1.0
    d2 = validate_and_coerce(_draft(confidence=-0.5))
    assert d2.confidence == 0.0
