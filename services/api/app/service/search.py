"""Cross-meeting search.

v1 is exact case-insensitive substring matching against each meeting's
`summary.json` and `transcript.json`. The artifacts are pulled in
parallel from B2 on every query — this is the load-bearing demo of the
B2 read path. v2 (embedding-based) is sketched in
`docs/exec-plans/active/embedding-search.md`.

Design rationale:

- We list `summary.json` keys to enumerate meetings (cheap, one S3 call).
- We fetch each summary in parallel; matches surface as `summary` hits.
- For misses we also fetch `transcript.json` (parallel) and scan segments
  so the query covers transcript content the summary may have elided.
- Snippets are extracted server-side so the response is renderable
  without the client having to re-fetch the whole artifact.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app.repo import (
    SUMMARY_KEY,
    TRANSCRIPT_KEY,
    get_artifact,
    list_summary_keys,
)
from app.types import SearchHit, SearchResponse

logger = logging.getLogger(__name__)

MAX_HITS = 50
SNIPPET_WINDOW = 80  # chars either side of the match


def _meeting_id_from_summary_key(key: str) -> str:
    parts = key.split("/")
    return parts[1] if len(parts) >= 3 else ""


def _snippet(text: str, query_lc: str) -> str:
    """Extract a ~160-char window centered on the first match of `query_lc`."""
    body = (text or "").strip()
    if not body:
        return ""
    idx = body.lower().find(query_lc)
    if idx < 0:
        return body[: 2 * SNIPPET_WINDOW]
    start = max(0, idx - SNIPPET_WINDOW)
    end = min(len(body), idx + len(query_lc) + SNIPPET_WINDOW)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{body[start:end]}{suffix}"


def _summary_title(summary: dict | None, meeting_id: str) -> str:
    """Best-effort title for a hit: first topic, else first decision, else id."""
    if not summary:
        return meeting_id
    topics = summary.get("topics") or []
    if topics:
        return topics[0][:80]
    decisions = summary.get("decisions") or []
    if decisions:
        return decisions[0][:80]
    body = summary.get("summary") or ""
    head = body.split(".", 1)[0].strip()
    return head[:80] if head else meeting_id


def _scan_summary(
    meeting_id: str, summary: dict | None, query_lc: str
) -> SearchHit | None:
    if not summary:
        return None
    haystack = "\n".join(
        [
            summary.get("summary") or "",
            *(summary.get("decisions") or []),
            *(summary.get("topics") or []),
        ]
    )
    if query_lc not in haystack.lower():
        return None
    return SearchHit(
        meeting_id=meeting_id,
        title=_summary_title(summary, meeting_id),
        created_at=str(summary.get("generated_at", "")),
        kind="summary",
        score=1.0,
        snippet=_snippet(haystack, query_lc),
        segment_id=None,
    )


def _scan_transcript(
    meeting_id: str,
    summary: dict | None,
    transcript: dict | None,
    query_lc: str,
) -> SearchHit | None:
    """Find the best transcript segment containing the query, if any."""
    if not transcript:
        return None
    segments = transcript.get("segments") or []
    for seg in segments:
        text = (seg.get("text") or "").lower()
        if query_lc in text:
            return SearchHit(
                meeting_id=meeting_id,
                title=_summary_title(summary, meeting_id),
                created_at=str(transcript.get("generated_at", "")),
                kind="transcript",
                score=1.0,
                snippet=_snippet(seg.get("text") or "", query_lc),
                segment_id=seg.get("id"),
            )
    return None


def _fetch_pair(meeting_id: str) -> tuple[str, dict | None, dict | None]:
    """Pull summary.json + transcript.json for one meeting (serial inside thread)."""
    summary = get_artifact(meeting_id, SUMMARY_KEY)
    transcript = get_artifact(meeting_id, TRANSCRIPT_KEY)
    return meeting_id, summary, transcript


def search(query: str, max_workers: int = 12) -> SearchResponse:
    """Cross-meeting substring search.

    Returns at most `MAX_HITS` hits, ordered by recency (newest first
    via the underlying summary key ordering). Empty query returns an
    empty response without a B2 round-trip.
    """
    q = (query or "").strip()
    if not q:
        return SearchResponse(query=q, hits=[], meetings_searched=0)
    query_lc = q.lower()

    summary_keys = list_summary_keys(max_keys=10_000)
    meeting_ids = [_meeting_id_from_summary_key(k) for k in summary_keys if k]
    meeting_ids = [m for m in meeting_ids if m]

    if not meeting_ids:
        return SearchResponse(query=q, hits=[], meetings_searched=0)

    hits: list[SearchHit] = []
    truncated = False
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for mid, summary, transcript in pool.map(_fetch_pair, meeting_ids):
            hit = _scan_summary(mid, summary, query_lc)
            if hit is None:
                hit = _scan_transcript(mid, summary, transcript, query_lc)
            if hit is not None:
                hits.append(hit)
                if len(hits) >= MAX_HITS:
                    truncated = True
                    break

    logger.info(
        "Search complete: query=%s meetings=%d hits=%d truncated=%s",
        q,
        len(meeting_ids),
        len(hits),
        truncated,
    )
    return SearchResponse(
        query=q,
        hits=hits,
        meetings_searched=len(meeting_ids),
        truncated=truncated,
    )
