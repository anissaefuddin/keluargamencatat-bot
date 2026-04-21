"""Voice transcription via faster-whisper.

The model loads lazily on first use and stays resident in the process.
Small multilingual model is ~500MB download, ~1GB RAM, CPU-friendly.
"""
import asyncio
from functools import lru_cache
from app.utils.logger import get_logger

log = get_logger(__name__)

_MODEL_SIZE = "small"  # balance: quality vs CPU speed; can downgrade to "base" if slow


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel
    log.info("whisper.loading", extra={"size": _MODEL_SIZE})
    m = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    log.info("whisper.loaded")
    return m


def _transcribe_sync(audio_path: str) -> tuple[str, float]:
    model = _get_model()
    segments, info = model.transcribe(
        audio_path,
        language="id",
        beam_size=1,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text, float(info.language_probability or 0.0)


async def transcribe(audio_path: str) -> tuple[str, float]:
    """Return (text, confidence). Empty text means failure."""
    return await asyncio.to_thread(_transcribe_sync, audio_path)
