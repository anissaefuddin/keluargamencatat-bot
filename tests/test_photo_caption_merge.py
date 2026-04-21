"""Test the photo+caption merge logic in isolation (no Telegram, no Ollama)."""
from unittest.mock import patch, AsyncMock
import pytest
from app.domain.models import TxnDraft
from app.ai import text_extractor


@pytest.mark.asyncio
async def test_categorize_description_from_caption():
    async def fake_chat_json(messages, model=None, timeout=45.0):
        return {
            "tipe_transaksi": "pengeluaran",
            "kategori": "makanan",
            "keterangan": "makan siang di warung",
        }

    with patch.object(text_extractor, "chat_json", fake_chat_json):
        res = await text_extractor.categorize_description("makan siang di warung")

    assert res["kategori"] == "makanan"
    assert res["tipe_transaksi"] == "pengeluaran"
    assert "makan siang" in res["keterangan"]


@pytest.mark.asyncio
async def test_categorize_empty_returns_defaults():
    res = await text_extractor.categorize_description("")
    assert res["kategori"] == "lainnya"
    assert res["tipe_transaksi"] == "pengeluaran"
    assert res["keterangan"] == ""


@pytest.mark.asyncio
async def test_categorize_llm_failure_falls_back_to_keywords():
    async def fake_chat_json(messages, model=None, timeout=45.0):
        from app.ai.ollama_client import OllamaError
        raise OllamaError("down")

    with patch.object(text_extractor, "chat_json", fake_chat_json):
        res = await text_extractor.categorize_description("makan di restoran")

    # regex_fallback keyword list maps "makan" → "makanan"
    assert res["kategori"] == "makanan"
