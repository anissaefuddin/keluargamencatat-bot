import base64
import json
import httpx
from app.config.settings import settings
from app.domain.models import TxnDraft
from app.domain.normalizer import parse_nominal, normalize_category
from app.utils.logger import get_logger

log = get_logger(__name__)


OCR_PROMPT = (
    "You are a receipt (struk belanja) reader. Look at the receipt image and "
    "extract ONLY the final total amount in Indonesian Rupiah and the merchant/toko name.\n\n"
    "Return ONLY a JSON object:\n"
    '{"total": <integer rupiah, no Rp>, "merchant": "<string>", "confidence": <0.0-1.0>}\n\n'
    "If you cannot read the total confidently, set total=0 and confidence=0.0."
)


async def extract_from_image(image_bytes: bytes, pengguna: str = "") -> TxnDraft | None:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    body = {
        "model": settings.ollama_vision_model,
        "prompt": OCR_PROMPT,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": 0.0, "num_predict": 256},
    }
    try:
        # First OCR may take 60-90s for LLaVA cold load on CPU
        async with httpx.AsyncClient(timeout=150.0) as client:
            r = await client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        log.warning("ocr.http_error", extra={"err": str(e)})
        return None

    content = data.get("response", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        log.warning("ocr.bad_json", extra={"content": content[:200]})
        return None

    total = int(parsed.get("total") or 0)
    # Cross-check via regex on the merchant/response text in case LLM returned "Rp 50.000"
    if total <= 0:
        re_n = parse_nominal(str(parsed.get("total", "")))
        if re_n:
            total = re_n
    if total <= 0:
        log.info("ocr.no_total")
        return None

    merchant = str(parsed.get("merchant") or "")[:80]
    keterangan = f"struk: {merchant}" if merchant else "struk"

    return TxnDraft(
        nominal=total,
        tipe_transaksi="pengeluaran",
        kategori=normalize_category(None),  # unknown; user will pick
        keterangan=keterangan,
        confidence=float(parsed.get("confidence") or 0.5),
        raw_input=keterangan,
        source="photo",
        pengguna=pengguna,
    )
