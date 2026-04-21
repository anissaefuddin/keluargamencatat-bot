import json
import httpx
from app.config.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class OllamaError(RuntimeError):
    pass


async def chat_json(messages: list[dict], model: str | None = None, timeout: float = 45.0) -> dict:
    """Call Ollama /api/chat with format=json; return parsed dict."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    body = {
        "model": model or settings.ollama_text_model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "num_predict": 128,
            "temperature": 0.1,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        log.warning("ollama.http_error", extra={"err": str(e)})
        raise OllamaError(str(e)) from e

    content = (data.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError("empty content")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        log.warning("ollama.bad_json", extra={"content": content[:200]})
        raise OllamaError(f"bad json: {e}") from e


async def warm_up() -> None:
    """Warm up the text model at boot. Vision model warms on first use."""
    try:
        await chat_json(
            [{"role": "user", "content": "ready?"}], timeout=120.0,
        )
        log.info("ollama.warm_up_ok")
    except Exception as e:
        log.warning("ollama.warm_up_failed", extra={"err": str(e)})
