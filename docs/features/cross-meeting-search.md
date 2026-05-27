<!-- last_verified: 2026-05-26 -->
# Feature: Cross-Meeting Search

## Purpose
Search across every meeting's summary and transcript stored in B2. v1 is exact case-insensitive substring matching with server-extracted snippets; v2 (embedding-based) is described in `docs/exec-plans/active/embedding-search.md`.

This is the load-bearing demo of B2 as a read-heavy system of record — every query reads many `summary.json` and `transcript.json` blobs directly from B2 with no application database in between.

## Used By
- UI: `/search` page
- API: `GET /search?q=...`

## Core Functions
- `service/search.py::search` — list summaries, parallel-read, scan, snippet
- `repo/meetings_store.py::list_summary_keys` — enumerate every `summary.json` key

## Canonical Files
- Pattern exemplar: `services/api/app/service/search.py`

## Inputs
- `q`: string (URL query param, max 500 chars)

## Outputs
- `SearchResponse`: `{ query, hits: [{ meeting_id, title, created_at, kind, score, snippet, segment_id? }], meetings_searched, truncated }`

## Flow
1. `list_summary_keys(max_keys=10_000)` enumerates the bucket
2. Parallel `_fetch_pair(meeting_id)` reads `summary.json` + `transcript.json` for each meeting
3. `_scan_summary` checks the concatenated summary / decisions / topics text for the lowercased query; on match, emits a `summary` hit
4. If no summary hit, `_scan_transcript` walks the segments and emits the first matching segment as a `transcript` hit (with `segment_id` for deep-linking)
5. Results returned newest-first, capped at `MAX_HITS=50` (the response's `truncated` flag flips when the cap is hit)

## Edge Cases
- Empty query -> empty response, no B2 round-trips
- No meetings in bucket -> empty response
- Query longer than 500 chars -> 400
- Pipeline still running for some meetings (no `summary.json` yet) -> those meetings simply don't contribute hits
- Query matches multiple segments in one meeting -> we return only the first match per meeting (v2 will return ranked-by-similarity)

## UX States
- No query submitted yet -> empty-state card "Type a query to search your meetings"
- Loading: skeletons
- Error: ErrorState with Retry
- Zero hits: empty-state showing the meeting-searched count

## Verification
- Test files: `services/api/tests/test_search.py`
- Required cases: empty query, substring match, no-hit case

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/exec-plans/active/embedding-search.md](../exec-plans/active/embedding-search.md)
