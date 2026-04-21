from app.ai.ollama_client import chat_json, OllamaError
from app.ai.prompts import build_messages
from app.ai.regex_fallback import extract_by_regex
from app.domain.models import TxnDraft
from app.domain.normalizer import normalize_category
from app.domain.validator import validate_and_coerce, ValidationError
from app.utils.logger import get_logger

log = get_logger(__name__)


async def extract(raw: str, pengguna: str = "") -> TxnDraft | None:
    """Return a validated TxnDraft, or None if unparseable."""
    raw = (raw or "").strip()
    if not raw:
        return None

    try:
        data = await chat_json(build_messages(raw))
        draft = TxnDraft(
            nominal=int(data.get("nominal") or 0),
            tipe_transaksi=data.get("tipe_transaksi") or "pengeluaran",
            kategori=normalize_category(data.get("kategori")),
            keterangan=(data.get("keterangan") or raw)[:200],
            confidence=float(data.get("confidence") or 0.5),
            raw_input=raw,
            source="text",
            pengguna=pengguna,
        )
        draft = validate_and_coerce(draft)
        log.info("ai.extract_ok", extra={"nominal": draft.nominal, "cat": draft.kategori, "conf": draft.confidence})
        return draft
    except (OllamaError, ValidationError, ValueError, TypeError) as e:
        log.warning("ai.extract_fallback", extra={"err": str(e)[:120]})

    # Regex fallback
    fb = extract_by_regex(raw)
    if fb:
        fb.pengguna = pengguna
        try:
            fb = validate_and_coerce(fb)
            return fb
        except ValidationError:
            return None
    return None
