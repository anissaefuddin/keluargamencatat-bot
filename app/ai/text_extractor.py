from app.ai.ollama_client import chat_json, OllamaError
from app.ai.prompts import build_messages
from app.ai.regex_fallback import extract_by_regex
from app.domain.models import TxnDraft
from app.domain.normalizer import parse_nominal, normalize_category
from app.domain.validator import validate_and_coerce, ValidationError
from app.utils.logger import get_logger

log = get_logger(__name__)


async def extract(raw: str, pengguna: str = "") -> TxnDraft | None:
    """Return a validated TxnDraft, or None if unparseable.

    Strategy: run LLM + deterministic regex, trust regex for nominal when
    they disagree. LLM is authoritative for category/tipe. This prevents
    hallucinated amounts and magnitude errors.
    """
    raw = (raw or "").strip()
    if not raw:
        return None

    regex_nominal = parse_nominal(raw)

    try:
        data = await chat_json(build_messages(raw))
        llm_nominal = int(data.get("nominal") or 0)

        # Cross-check: if regex found one, it wins; if regex found none and LLM
        # also returned 0/tiny, the message has no amount → bail to fallback.
        if regex_nominal is not None:
            nominal = regex_nominal
            conf = float(data.get("confidence") or 0.5)
            if llm_nominal != regex_nominal:
                conf = min(conf, 0.7)
                log.info("ai.nominal_mismatch", extra={"llm": llm_nominal, "regex": regex_nominal})
        elif llm_nominal > 0:
            # No regex hit but LLM claims a number — don't trust it, it may be hallucinated.
            log.warning("ai.llm_only_nominal_rejected", extra={"llm": llm_nominal, "raw": raw[:80]})
            return None
        else:
            return None

        draft = TxnDraft(
            nominal=nominal,
            tipe_transaksi=data.get("tipe_transaksi") or "pengeluaran",
            kategori=normalize_category(data.get("kategori")),
            keterangan=(data.get("keterangan") or raw)[:200],
            confidence=conf,
            raw_input=raw,
            source="text",
            pengguna=pengguna,
        )
        draft = validate_and_coerce(draft)
        log.info("ai.extract_ok", extra={"nominal": draft.nominal, "cat": draft.kategori, "conf": draft.confidence})
        return draft
    except (OllamaError, ValidationError, ValueError, TypeError) as e:
        log.warning("ai.extract_fallback", extra={"err": str(e)[:120]})

    # Regex fallback (LLM unavailable or failed)
    fb = extract_by_regex(raw)
    if fb:
        fb.pengguna = pengguna
        try:
            return validate_and_coerce(fb)
        except ValidationError:
            return None
    return None
