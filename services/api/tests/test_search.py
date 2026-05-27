"""Smoke tests for cross-meeting search."""

import pytest

from app.service import search as search_service


@pytest.mark.asyncio
async def test_empty_query_returns_empty(client):
    response = await client.get("/search?q=")
    assert response.status_code == 200
    data = response.json()
    assert data["hits"] == []
    assert data["meetings_searched"] == 0


@pytest.mark.asyncio
async def test_search_substring_match(client, monkeypatch):
    """Matching summary substring produces a hit."""
    monkeypatch.setattr(
        search_service, "list_summary_keys", lambda max_keys: ["meetings/m1/summary.json"]
    )

    def fake_get_artifact(meeting_id, artifact):
        if artifact == "summary.json":
            return {
                "summary": "Decided to launch the new onboarding flow next week.",
                "decisions": ["Ship onboarding"],
                "topics": ["product", "onboarding"],
                "generated_at": "2026-05-26T00:00:00Z",
            }
        return None

    monkeypatch.setattr(search_service, "get_artifact", fake_get_artifact)

    response = await client.get("/search?q=onboarding")
    assert response.status_code == 200
    data = response.json()
    assert data["meetings_searched"] == 1
    assert len(data["hits"]) == 1
    hit = data["hits"][0]
    assert hit["meeting_id"] == "m1"
    assert hit["kind"] == "summary"
    assert "onboarding" in hit["snippet"].lower()
