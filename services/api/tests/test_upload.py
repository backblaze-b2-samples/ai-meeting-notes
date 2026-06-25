"""Regression tests for the legacy upload route."""

import pytest

from app.runtime import upload as upload_runtime


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", ["bad-value", "-1"])
async def test_upload_rejects_invalid_content_length(
    client, monkeypatch, content_length
):
    def fail_upload(*_args, **_kwargs):
        raise AssertionError("upload processing should not run")

    monkeypatch.setattr(upload_runtime, "process_meeting_upload", fail_upload)

    response = await client.post(
        "/upload",
        headers={"Content-Length": content_length},
        files={"file": ("meeting.mp3", b"audio", "audio/mpeg")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Content-Length header"}
