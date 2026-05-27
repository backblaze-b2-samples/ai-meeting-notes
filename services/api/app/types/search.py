"""Pydantic models for cross-meeting search.

v1 search is exact substring match over each meeting's `summary.json` and
`transcript.json`. The shape is forward-compatible with embedding-based
search (see `docs/exec-plans/active/embedding-search.md`): a score field
is present, snippets are extracted server-side, and the `kind` field
identifies which artifact each hit came from.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

HitKind = Literal["summary", "transcript", "title"]


class SearchHit(BaseModel):
    """A single hit inside a single meeting.

    `score` is a float in [0, 1] — for v1 substring matching the score is
    1.0 for any match. `snippet` is a ~160-character window centered on
    the first match. `segment_id` is populated when `kind == "transcript"`
    so the UI can deep-link to a particular speaker turn.
    """

    meeting_id: str
    title: str
    created_at: str
    kind: HitKind
    score: float
    snippet: str
    segment_id: str | None = None


class SearchResponse(BaseModel):
    """Wraps the hit list with the query that produced it.

    Returning `query` makes the response self-describing for clients that
    cache results out-of-band (e.g., a debug panel showing the resolved
    query for the current view).
    """

    query: str
    hits: list[SearchHit]
    meetings_searched: int
    truncated: bool = False
