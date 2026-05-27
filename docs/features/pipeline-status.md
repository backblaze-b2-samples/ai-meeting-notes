<!-- last_verified: 2026-05-27 -->
# Feature: Pipeline Status

## Purpose
Surface the per-meeting pipeline state to the UI so a user can watch a meeting move from `queued` -> `transcribing` -> `summarizing` -> `done` (or `failed`) without refreshing.

## Used By
- UI: `/meetings/<id>` detail page (pipeline-status strip)
- API: `GET /meetings/{id}/status`

## Core Functions
- `service/pipeline.py::_write_status` — rewrites `status.json` at every state change
- `service/meeting.py::get_meeting_status`
- `apps/web/src/lib/queries.ts::useMeetingStatus` — polls every 2.5s until terminal
- `apps/web/src/components/meetings/pipeline-status.tsx`

## Canonical Files
- Pattern exemplar: `services/api/app/service/pipeline.py` (the `_run_<stage>` chain)

## Inputs
- `meeting_id`: path param

## Outputs
- `MeetingStatus` Pydantic model serialized as JSON:
  ```json
  {
    "meeting_id": "abc123",
    "state": "summarizing",
    "stages": {
      "upload":  { "status": "done",    ... },
      "asr":     { "status": "done",    ... },
      "summary": { "status": "running", ... },
      "actions": { "status": "pending", ... }
    },
    "error": null,
    "updated_at": "2026-05-26T14:23:00Z",
    "transcription_provider": "assemblyai",
    "llm_model": "claude-haiku-4-5-20251001"
  }
  ```

## Flow
1. Upload writes `status.json` with `state=queued` synchronously
2. ASR stage rewrites it to `state=transcribing` *before* calling the provider
3. Same pattern for summary and actions stages
4. On any provider, LLM, or unexpected in-process exception, `state=failed` with the error message persisted
5. UI polls `/meetings/{id}/status` every 2.5s; the refetch interval returns `false` once `state` is `done` or `failed`

## Edge Cases
- Polling a meeting that doesn't exist -> 404 (the UI shows ErrorState)
- `status.json` missing immediately after upload (very narrow race) -> 404; UI retries
- Multiple browser tabs polling the same meeting -> TanStack Query dedupes via the shared `qk.meetingStatus(id)` key

## UX States
- Pre-terminal -> `PipelineStatus` strip visible with per-stage icons
- Terminal (`done`) -> strip hides itself; the artifacts render directly
- Terminal (`failed`) -> strip stays visible with the red icon + error message

## Verification
- Test files: `services/api/tests/test_meetings.py` (smoke test the endpoint)
- Manual smoke: upload a meeting, watch the badge transitions in the dashboard's Recent Meetings table

## Related Docs
- [README.md](../../README.md)
- [docs/RELIABILITY.md](../RELIABILITY.md)
