"""Edge TTS fallback provider — free text-to-speech via Microsoft Edge neural voices.

Used as a fallback when Bhashini API key is not available.
Supports 10+ Indian languages with female neural voices.
"""

from __future__ import annotations

import time

import edge_tts
from loguru import logger


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class EdgeTTSError(Exception):
    """Raised on any Edge TTS failure."""


# ---------------------------------------------------------------------------
# FR-2: Voice mapping — Indian languages → Microsoft Edge neural voices
# ---------------------------------------------------------------------------

EDGE_TTS_VOICES: dict[str, str] = {
    "hi": "hi-IN-SwaraNeural",
    "bn": "bn-IN-TanishaaNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "mr": "mr-IN-AarohiNeural",
    "gu": "gu-IN-DhwaniNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "pa": "pa-IN-GurpreetNeural",
    "ur": "ur-IN-GulNeural",
}


# ---------------------------------------------------------------------------
# FR-2: Helper to get voice for a language code
# ---------------------------------------------------------------------------


def get_voice_for_language(language_code: str) -> str | None:
    """Return the Edge TTS voice name for a language code, or None if unsupported."""
    return EDGE_TTS_VOICES.get(language_code)


# ---------------------------------------------------------------------------
# FR-3: edge_text_to_speech — async TTS via edge-tts
# ---------------------------------------------------------------------------


async def edge_text_to_speech(
    text: str,
    language_code: str,
    request_id: str = "",
) -> bytes:
    """Convert text to speech audio bytes using Microsoft Edge TTS.

    Returns MP3 audio bytes.
    Raises ValueError on invalid inputs.
    Raises EdgeTTSError on TTS failure or unsupported language.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not language_code:
        raise ValueError("language_code must be a non-empty string")

    voice = get_voice_for_language(language_code)
    if voice is None:
        raise EdgeTTSError(f"Language '{language_code}' is not supported by Edge TTS")

    logger.info(
        "Edge TTS request | request_id={} | language={} | voice={} | text_length={}",
        request_id,
        language_code,
        voice,
        len(text),
    )

    start = time.monotonic()
    audio_chunks: list[bytes] = []

    try:
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
    except Exception as exc:
        logger.error(
            "Edge TTS failed | request_id={} | error={}",
            request_id,
            type(exc).__name__,
        )
        raise EdgeTTSError(f"Edge TTS failed: {exc}") from exc

    audio_bytes = b"".join(audio_chunks)

    if not audio_bytes:
        raise EdgeTTSError("Edge TTS returned empty audio")

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "Edge TTS success | request_id={} | audio_bytes={} | latency_ms={:.0f}",
        request_id,
        len(audio_bytes),
        elapsed_ms,
    )

    return audio_bytes
