"""HTTP surface for cross-meeting search.

A single endpoint — `GET /search?q=...` — that pulls summaries and
transcripts straight out of B2 on every query. This is the load-bearing
demo of B2 as a read-heavy system of record for meeting history.
"""

from fastapi import APIRouter, HTTPException, Query

from app.service.search import search
from app.types import SearchResponse

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search_endpoint(q: str = Query(default="", max_length=500)):
    """Substring search across every meeting's summary + transcript."""
    if len(q) > 500:
        raise HTTPException(status_code=400, detail="Query too long")
    return search(q)
