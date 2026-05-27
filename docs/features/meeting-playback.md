<!-- last_verified: 2026-05-26 -->
# Feature: Meeting Playback

## Purpose
Synced inline player + click-to-seek transcript with current-segment highlight so a user can scrub through a meeting by speaker turn.

## Used By
- UI: `/meetings/<id>` page (`apps/web/src/app/meetings/[id]/page.tsx`)
- API:
  - `GET /meetings/{id}/playback` — inline presigned URL
  - `GET /meetings/{id}/download` — attachment presigned URL
  - `GET /meetings/{id}/transcript` — speaker-turn list

## Core Functions
- `service/meeting.py::get_playback_url` / `get_download_url`
- `repo/meetings_store.py::presign_recording_playback`
- `apps/web/src/components/meetings/transcript-view.tsx`
- `apps/web/src/components/meetings/waveform.tsx`

## Canonical Files
- Pattern exemplar: `apps/web/src/app/meetings/[id]/page.tsx` (the player + transcript wiring)

## Inputs
- `meeting_id`: path param

## Outputs
- `GET /meetings/{id}/playback` -> `{ url, expires_in }` — inline presigned GET, no Content-Disposition
- `GET /meetings/{id}/download` -> `{ url, expires_in }` — presigned GET with `Content-Disposition: attachment`
- `GET /meetings/{id}/transcript` -> `Transcript` (segments, speakers, language, duration_ms, provider)

## Flow
- Detail page fetches playback URL via `getMeetingPlaybackUrl(id)` on mount
- `<audio controls>` plays the presigned URL; `onTimeUpdate` updates `currentTimeMs`
- Transcript view groups adjacent same-speaker segments into turns, renders each line as a `<button>` that calls `handleSeek(segment.start_ms)`
- Active segment is the one whose `[start_ms, end_ms)` brackets `currentTimeMs`; it gets the highlight class
- Action items expose a "Source" jump-link back to the transcript via the same seek path

## Edge Cases
- Playback URL 404 (recording uploaded but listing hasn't propagated) -> silent (no toast), the `<audio>` stays in its loading skeleton
- Presigned URL expired (10-min) -> the next interaction re-fetches
- Missing transcript -> "No transcript available" placeholder; seek is a no-op
- Video recording -> the same `<audio>` element renders just the audio track; video preview is a deferred feature

## UX States
- Empty (no recording): playback skeleton + transcript empty-state
- Loading: skeletons for both
- Error: ErrorState on transcript fetch with Retry; toast for playback URL failure

## Verification
- Manual smoke: upload a recording, open the detail page, click a transcript line, confirm the player seeks
- E2E: `apps/web/e2e/upload.spec.ts` covers nav to the meetings page

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
- [docs/features/summary-action-items.md](summary-action-items.md)
