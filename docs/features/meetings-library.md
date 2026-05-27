<!-- last_verified: 2026-05-26 -->
# Feature: Meetings Library

## Purpose
Browse every meeting stored in B2 as a grid of cards — title, pipeline state, summary excerpt — with deep links into each meeting's detail page.

## Used By
- UI: `/meetings` page
- API:
  - `GET /meetings`
  - `DELETE /meetings/{id}`

## Core Functions
- `service/meeting.py::list_meeting_rows` — list recording.* keys, parallel-read status.json + summary.json
- `service/meeting.py::remove_meeting` — cascade delete the whole bundle
- `repo/meetings_store.py::list_meetings`, `delete_meeting`

## Canonical Files
- Pattern exemplar: `apps/web/src/components/meetings/meeting-card.tsx`
- Service orchestration: `services/api/app/service/meeting.py`

## Inputs
- `limit`: int (query param on `GET /meetings`, default 100, max 500)
- `meeting_id`: path param, must match `^[A-Za-z0-9_-]{6,64}$`

## Outputs
- `GET /meetings` -> `Meeting[]` sorted newest-first
- `DELETE /meetings/{id}` -> `{ deleted: string[], errors: { Key, Code, Message }[] }` — cascade delete every key under `meetings/<id>/`

## Flow
1. `GET /meetings` -> `list_objects_v2(Prefix="meetings/")` filtered to keys matching `meetings/<id>/recording.*`
2. Sorted newest-first, sliced to `limit`
3. Parallel fetch of each meeting's `status.json` + `summary.json` (so the card shows current state + excerpt)
4. Shaped into `Meeting[]`

## Edge Cases
- Recording present but `status.json` missing -> `state=queued` fallback (very narrow race)
- Summary excerpt absent -> card shows "Summary not available yet" or the failure error
- Pipeline `failed` -> red badge + error message on the card
- Bulk delete of a single meeting cascades the whole prefix (recording + 4 JSON artifacts)

## UX States
- Empty: "No meetings yet" with upload CTA
- Loading: 6 skeletons
- Error: ErrorState with Retry button

## Verification
- Test files: `services/api/tests/test_meetings.py`
- Required cases: empty bucket; happy-path listing; missing artifacts

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
- [docs/features/meeting-upload.md](meeting-upload.md)
