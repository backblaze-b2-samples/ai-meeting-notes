<!-- last_verified: 2026-05-26 -->
# Feature: Dashboard

## Purpose
Meeting-centric overview of B2 storage activity: total meetings, total transcribed minutes, open action items, uploads today, pipeline-state breakdown, recent meetings, and a 7-day activity chart.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /files/stats`, `GET /meetings`, `GET /files/stats/activity`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx` — 4 stat cards: Meetings, Transcribed Time, Open Action Items, Uploads Today
- `apps/web/src/components/dashboard/format-breakdown.tsx` — pipeline state chips (Done / Transcribing / Summarizing / Queued / Failed)
- `apps/web/src/components/dashboard/recent-uploads-table.tsx` — last 10 meetings with state + Open link
- `apps/web/src/components/dashboard/upload-chart.tsx` — 7-day meetings-uploaded chart with a Uploads / Minutes toggle
- `apps/web/src/lib/api-client.ts` — `getFileStats()`, `listMeetings()`, `getUploadActivity()`
- `services/api/app/runtime/files.py` — `GET /files/stats` handler
- `services/api/app/service/files.py` — `get_stats()` merges bucket-level totals with meeting aggregates
- `services/api/app/service/meeting.py` — `aggregate_for_dashboard()` totals the `meetings/` prefix

## Canonical Files
- Dashboard page layout: `apps/web/src/components/dashboard/dashboard-view.tsx`
- Stats service logic: `services/api/app/service/files.py`

## Inputs
- None (dashboard loads data automatically)

## Outputs
- `GET /files/stats` -> `UploadStats` (`total_files`, `total_size_bytes`, `total_size_human`, `uploads_today`, `total_downloads`, `total_meetings`, `total_duration_ms`, `meetings_size_bytes`, `meetings_size_human`, `open_action_items`, `meetings_by_state`)
- `GET /meetings` (limit 10) -> `Meeting[]` for recent meetings table
- `GET /files/stats/activity?days=7` -> `DailyUploadCount[]` for chart (server-side aggregation)

## Flow
- Page loads -> three parallel API calls (stats, recent meetings, upload activity)
- Stats cards display: Meetings (count), Transcribed Time (formatted `m:ss` / `h:mm:ss`), Open Action Items, Uploads Today
- Pipeline state chips display per-state meeting counts
- Upload chart displays server-aggregated daily meeting counts for last 7 days as a bar chart
- Recent meetings table shows last 10 meetings with filename, state badge, date, Open link

## Edge Cases
- API unavailable -> stats default to zeros, table shows empty state
- No meetings uploaded -> empty hero card, no table or chart visible
- Large meeting count -> stats endpoint paginates via `ContinuationToken`

## UX States
- Loading: skeleton placeholders for cards and table
- Empty: hero card with CTA
- Loaded: populated cards, chart, table

## Verification
- Test files: `services/api/tests/test_meetings.py`
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
