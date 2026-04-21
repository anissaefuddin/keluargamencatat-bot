"""Cross-check logic tests that don't require Ollama."""
from unittest.mock import patch
import pytest
from app.ai import text_extractor


@pytest.mark.asyncio
async def test_reject_llm_hallucinated_nominal_when_regex_finds_none():
    """If the raw text has no digits+unit and LLM still claims a nominal,
    reject the draft rather than writing a fabricated amount."""
    async def fake_chat_json(messages, model=None, timeout=20.0):
        return {
            "nominal": 50000,
            "tipe_transaksi": "pengeluaran",
            "kategori": "tagihan",
            "keterangan": "listrik",
            "confidence": 0.98,
        }

    with patch.object(text_extractor, "chat_json", fake_chat_json):
        draft = await text_extractor.extract("bayar listrik", pengguna="@t")

    assert draft is None


@pytest.mark.asyncio
async def test_regex_wins_on_magnitude_mismatch():
    """If LLM says 200000 but regex parses '20 ribu' as 20000, prefer regex,
    and downgrade confidence so user gets a confirmation prompt."""
    async def fake_chat_json(messages, model=None, timeout=20.0):
        return {
            "nominal": 200000,  # wrong magnitude
            "tipe_transaksi": "pengeluaran",
            "kategori": "makanan",
            "keterangan": "kopi",
            "confidence": 0.95,
        }

    with patch.object(text_extractor, "chat_json", fake_chat_json):
        draft = await text_extractor.extract("kopi 20 ribu", pengguna="@t")

    assert draft is not None
    assert draft.nominal == 20000
    assert draft.confidence <= 0.7
    assert draft.kategori == "makanan"
