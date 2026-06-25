<!-- last_verified: 2026-05-27 -->
# Feature: Meeting Upload

## Purpose
Accept a meeting recording (audio or video), durably persist it to B2 under a fresh per-meeting prefix, and kick off the transcription -> summary -> actions pipeline as a background task.

## Used By
- UI: `/upload` page (drag-and-drop)
- API: `POST /meetings` (canonical), `POST /upload` (legacy alias)
- Job: FastAPI BackgroundTask (`service/pipeline.py::run_pipeline`)

## Core Functions
- `service/meeting.py::init_meeting` — write recording + initial `status.json`
- `service/pipeline.py::run_pipeline` — background ASR -> summary -> actions
- `service/upload.py::process_meeting_upload` — legacy upload path validation
- `repo/meetings_store.py::put_recording`, `put_artifact` — B2 writes

## Canonical Files
- Pattern exemplar: `services/api/app/runtime/meetings.py::create_meeting_endpoint`

## Inputs
- multipart form file (browser)
- `file.content_type` — must be audio/* or one of the accepted video types
- `file.filename` — sanitized + extension-checked before writing

## Outputs
- `Meeting` (Pydantic) — the listing-shape row for the freshly created meeting
- Side effects:
  - PUT `meetings/<id>/recording.<ext>`
  - PUT `meetings/<id>/status.json` (state=queued)
  - BackgroundTask spawned to run the pipeline

## Flow
1. Client POSTs multipart `file` to `/meetings`
2. API streams the file, enforcing the 100MB size cap
3. `init_meeting` mints a fresh id, writes the recording, writes `status.json` with `state=queued`
4. Background task starts `run_pipeline(meeting_id, file_data)`
5. Response returns the `Meeting` row so the UI can navigate to `/meetings/<id>` and begin polling status

## Edge Cases
- Unsupported extension -> 415 with detail, no B2 write
- Empty file -> 400
- Malformed `Content-Length` on legacy `/upload` -> 400, no B2 write
- File > 100MB -> 413 with size detail
- B2 write failure -> 502 with the underlying error (no pipeline kicked)
- Pipeline failure -> `status.json` marked `failed`, recording is preserved for re-upload / retry

## UX States
- Empty: dropzone with "Drag & drop a meeting recording" prompt
- Loading: per-file progress bar
- Error: red status icon + toast with the API's detail message

## Verification
- Test files: `services/api/tests/test_meetings.py`, `services/api/tests/test_upload.py`, `services/api/tests/test_structure.py`
- Required cases: happy path; bad extension; empty file; malformed `Content-Length`; meeting id validation
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: meetings list endpoint returns the new row immediately after POST; status.json exists with `state=queued`

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
- [docs/features/pipeline-status.md](pipeline-status.md)
