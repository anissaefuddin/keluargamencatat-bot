import time
from unittest.mock import patch
from app.state import nominal_await_store


def setup_function(_):
    nominal_await_store._store.clear()


def test_set_and_peek():
    nominal_await_store.set_waiting(42, {"kategori": "makanan", "pengguna": "@a"})
    p = nominal_await_store.peek_waiting(42)
    assert p is not None
    assert p["kategori"] == "makanan"
    assert nominal_await_store.is_waiting(42)


def test_pop_clears():
    nominal_await_store.set_waiting(42, {"kategori": "makanan"})
    popped = nominal_await_store.pop_waiting(42)
    assert popped is not None
    assert not nominal_await_store.is_waiting(42)
    assert nominal_await_store.pop_waiting(42) is None


def test_clear_returns_bool():
    assert nominal_await_store.clear_waiting(42) is False
    nominal_await_store.set_waiting(42, {"kategori": "makanan"})
    assert nominal_await_store.clear_waiting(42) is True
    assert nominal_await_store.clear_waiting(42) is False


def test_ttl_expiry():
    nominal_await_store.set_waiting(42, {"kategori": "makanan"})
    # Age the entry past TTL
    ts, data = nominal_await_store._store[42]
    nominal_await_store._store[42] = (ts - 400, data)
    assert not nominal_await_store.is_waiting(42)
    assert nominal_await_store.peek_waiting(42) is None


def test_multi_user_isolation():
    nominal_await_store.set_waiting(1, {"kategori": "makanan"})
    nominal_await_store.set_waiting(2, {"kategori": "transport"})
    assert nominal_await_store.peek_waiting(1)["kategori"] == "makanan"
    assert nominal_await_store.peek_waiting(2)["kategori"] == "transport"
    nominal_await_store.pop_waiting(1)
    assert nominal_await_store.is_waiting(2)
