from types import SimpleNamespace

import pytest

from app.repo import transcription


def test_transcribe_wraps_sdk_exceptions(monkeypatch):
    seen = {}

    class FakeTranscriber:
        def __init__(self, config):
            seen["config"] = config
            self.config = config

        def transcribe(self, audio):
            seen["has_read"] = hasattr(audio, "read")
            raise RuntimeError("network unavailable")

    fake_aai = SimpleNamespace(
        TranscriptionConfig=lambda **kwargs: kwargs,
        Transcriber=FakeTranscriber,
    )
    monkeypatch.setattr(transcription, "_assemblyai_client", lambda: fake_aai)

    with pytest.raises(
        transcription.TranscriptionError,
        match="AssemblyAI request failed: network unavailable",
    ):
        transcription.transcribe(b"audio")

    assert seen["has_read"] is True
    assert seen["config"]["speech_models"] == [
        transcription.DEFAULT_ASSEMBLYAI_SPEECH_MODEL
    ]
