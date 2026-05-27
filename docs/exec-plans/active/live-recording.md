<!-- last_verified: 2026-05-26 -->
# Live Recording (browser MediaRecorder)

> Status: **Deferred** — v1 is upload-only. This plan documents the path.

## Goal
Let the user record a meeting in the browser via `MediaRecorder`, chunk-upload to B2 while recording, and trigger the same transcription pipeline on stop.

## Why deferred
Live recording brings in:
- `getUserMedia` permission UI, device picker, mute UI
- Chunked / resumable upload to B2 (multipart) with tab-close recovery
- A waveform / VU meter that's actually live
- Edge cases for browser navigation, tab-suspend, mid-record errors

That's a meaningful UI subsystem on its own. Building it before the
upload-only pipeline is solid would crowd out the B2 + ASR + LLM story
this sample is trying to tell.

## Sketch
- Frontend: a new `/record` route with a `<RecordButton>` that pipes
  `MediaRecorder` chunks into B2 multipart upload parts. The `meeting_id`
  is minted on Start; the first chunk's response carries the id so the
  detail page can pre-render before recording ends.
- Backend:
  - `POST /meetings/multipart/start` -> `{ meeting_id, upload_id }`
  - `POST /meetings/{id}/multipart/{part_number}` (binary body)
  - `POST /meetings/{id}/multipart/complete` -> kicks the pipeline
- The recorded artifact still lands at `meetings/<id>/recording.webm` so
  the rest of the pipeline is unchanged.

## Rough effort
1-2 weeks for a clean v1 (no edits, no pause/resume polish).
