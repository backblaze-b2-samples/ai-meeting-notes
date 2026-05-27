"""Smoke tests for the meetings routes.

These exercise the runtime/service wiring without touching the LLM or
transcription providers — the pipeline kickoff is stubbed so each
request returns synchronously and we can assert against the response
shape.
"""

from datetime import UTC, datetime

import pytest

from app.repo import MEETING_ID_RE
from app.service import meeting as meeting_service


@pytest.mark.asyncio
async def test_meeting_id_validation():
    """validate_meeting_id rejects malformed ids and accepts the canonical shape."""
    from app.service.meeting import MeetingIdError, validate_meeting_id

    for bad in ["", "..", "a/b", "short", "x" * 100, "with spaces"]:
        with pytest.raises(MeetingIdError):
            validate_meeting_id(bad)

    # Canonical shape: 6-64 chars, alnum + - + _
    validate_meeting_id("abc123")
    validate_meeting_id("hex-id_1234567890")


@pytest.mark.asyncio
async def test_list_meetings_returns_empty(client, monkeypatch):
    """An empty bucket lists an empty meetings array."""
    monkeypatch.setattr(meeting_service, "list_meetings", lambda max_keys: [])
    monkeypatch.setattr(
        meeting_service, "get_artifacts_parallel", lambda ids, art: {}
    )

    response = await client.get("/meetings")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_meeting_404(client, monkeypatch):
    """A missing meeting returns 404."""
    monkeypatch.setattr(meeting_service, "head_recording", lambda mid: None)
    response = await client.get("/meetings/abc123def456")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_meeting_listing_shape(client, monkeypatch):
    """`GET /meetings/{id}` returns the listing shape for a known meeting."""
    head = {
        "Key": "meetings/abc123def456/recording.mp3",
        "Size": 1024,
        "LastModified": datetime.now(UTC),
    }
    monkeypatch.setattr(meeting_service, "head_recording", lambda mid: head)
    monkeypatch.setattr(meeting_service, "get_artifact", lambda mid, art: None)

    response = await client.get("/meetings/abc123def456")
    assert response.status_code == 200
    data = response.json()
    assert data["meeting_id"] == "abc123def456"
    assert data["recording_key"] == head["Key"]
    assert data["state"] == "queued"


def test_meeting_id_regex_canonical():
    """The exported regex matches a fresh meeting id."""
    mid = meeting_service.new_meeting_id()
    assert MEETING_ID_RE.match(mid), mid
