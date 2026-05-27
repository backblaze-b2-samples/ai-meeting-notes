"""AssemblyAI transcription adapter.

Exposes a single function — `transcribe(audio_bytes)` — that returns a
provider-neutral raw dict. The service layer shapes it into a
`Transcript` Pydantic model so callers in `service/` never see SDK-shaped
payloads.

We use AssemblyAI exclusively for transcription so the sample
demonstrates diarized output by default. The SDK client is built lazily
and cached so a missing key only fails when transcription is actually
invoked.
"""

from __future__ import annotations

import functools
import io
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ASSEMBLYAI_SPEECH_MODEL = "universal-2"


# Public adapter shape — what service/ consumes. Provider-neutral.
# Keys mirror the Pydantic Transcript model so the service layer can
# unpack via `Transcript(**transcribe(...))` after adding `meeting_id`
# and `generated_at`.
TranscriptDict = dict[str, Any]


class TranscriptionError(RuntimeError):
    """Raised when transcription fails (provider error, missing key, etc.)."""


@functools.lru_cache(maxsize=1)
def _assemblyai_client():
    try:
        import assemblyai as aai
    except ImportError as e:
        raise TranscriptionError(
            "assemblyai package not installed — `pip install assemblyai`"
        ) from e
    key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    if not key:
        raise TranscriptionError("ASSEMBLYAI_API_KEY is not set")
    aai.settings.api_key = key
    return aai


def _ms(seconds: float | int | None) -> int:
    if seconds is None:
        return 0
    return round(float(seconds) * 1000)


def transcribe(audio_bytes: bytes) -> TranscriptDict:
    """Diarized transcription via AssemblyAI.

    Uploads the audio bytes, requests `speaker_labels=True`, and returns
    one segment per AssemblyAI "utterance". An utterance is bound to a
    single speaker, so we can carry it straight through to the
    SpeakerTurn list as well.

    Raises `TranscriptionError` on any failure (missing key, SDK absent,
    provider 4xx/5xx). Callers in service/ catch this and write a
    `status.json` with `state=failed`.
    """
    started = datetime.now(UTC).isoformat()
    logger.info("Transcription started: provider=assemblyai ts=%s", started)

    aai = _assemblyai_client()
    config = aai.TranscriptionConfig(
        speaker_labels=True,
        speech_models=[DEFAULT_ASSEMBLYAI_SPEECH_MODEL],
    )
    transcriber = aai.Transcriber(config=config)
    try:
        transcript = transcriber.transcribe(io.BytesIO(audio_bytes))
    except Exception as e:
        raise TranscriptionError(f"AssemblyAI request failed: {e}") from e

    if transcript.status == "error":
        raise TranscriptionError(
            f"AssemblyAI failed: {transcript.error or 'unknown error'}"
        )

    segments: list[dict] = []
    speakers: set[str] = set()
    utterances = getattr(transcript, "utterances", None) or []
    for i, utt in enumerate(utterances):
        speaker = f"Speaker {utt.speaker}" if utt.speaker else "Speaker 1"
        speakers.add(speaker)
        segments.append(
            {
                "id": f"u{i:05d}",
                "speaker": speaker,
                "start_ms": int(utt.start or 0),
                "end_ms": int(utt.end or 0),
                "text": (utt.text or "").strip(),
                "confidence": float(utt.confidence)
                if utt.confidence is not None
                else None,
            }
        )

    # Fallback: no utterances came back (very short clip), use the whole-text path.
    if not segments and getattr(transcript, "text", None):
        speakers.add("Speaker 1")
        segments.append(
            {
                "id": "u00000",
                "speaker": "Speaker 1",
                "start_ms": 0,
                "end_ms": int(getattr(transcript, "audio_duration", 0) * 1000),
                "text": transcript.text.strip(),
                "confidence": None,
            }
        )

    result = {
        "language": getattr(transcript, "language_code", None),
        "duration_ms": _ms(getattr(transcript, "audio_duration", None)),
        "segments": segments,
        "speakers": sorted(speakers),
        "provider": "assemblyai",
    }
    logger.info(
        "Transcription complete: provider=assemblyai segments=%d",
        len(segments),
    )
    return result
