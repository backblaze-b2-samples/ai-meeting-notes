<!-- last_verified: 2026-05-26 -->
# App Workflows

User journeys inside the application.

## Upload a Meeting Recording

- User navigates to `/upload`
- Drops or selects an audio or video meeting recording in the dropzone
- Client validates file size (max 100MB) and accepts `.wav .mp3 .flac .ogg .m4a .aac .opus .mp4 .mov .webm`
- Progress bar shows per-file upload status
- API validates the recording, mints a fresh meeting id, writes `meetings/<id>/recording.<ext>` and `meetings/<id>/status.json` (state=`queued`) to B2, then kicks off the transcription pipeline as a FastAPI BackgroundTask
- Response carries the freshly-built `Meeting` row so the UI can navigate straight to `/meetings/<id>` and begin polling status
- On success: toast notification, the meeting appears in `/meetings`
- On failure: red status icon with error message
- See: [Meeting Upload](features/meeting-upload.md), [Pipeline Status](features/pipeline-status.md)

## Browse Meetings

- User navigates to `/meetings`
- Page loads the meeting list from `GET /meetings` (sorted newest-first)
- Each `MeetingCard` shows: filename, created date, size, pipeline state badge (Queued / Transcribing / Summarizing / Done / Failed), and a one-line summary excerpt when the LLM stage has completed
- **Open** -> navigates to `/meetings/<id>`
- **Delete**: AlertDialog confirms; on accept, `DELETE /meetings/<id>` cascade-deletes the recording + JSON artifacts and TanStack Query invalidates the meetings + stats caches
- Empty bucket shows "No meetings yet" with an upload prompt
- See: [Meetings Library](features/meetings-library.md)

## View a Meeting

- User navigates to `/meetings/<id>` (from the grid, the dashboard "Recent Meetings" table, or a search hit)
- Page loads in parallel: the meeting row, `status.json`, transcript, summary, and actions
- A short-lived presigned URL is fetched for inline playback (`GET /meetings/<id>/playback`)
- The pipeline-status strip is visible while the pipeline is non-terminal; it polls `/meetings/<id>/status` every 2.5s via TanStack Query and hides itself once the state is `done`
- Transcript view renders speaker turns with click-to-seek; the active segment highlights as the player advances
- Summary panel shows the LLM summary, list of decisions, and topic chips
- Action items list shows the extracted actions with checkboxes (client-side state for v1) and a "Source" jump-link back to the transcript
- **Download recording**: button in the header fetches `/meetings/<id>/download` and opens the presigned URL in a new tab
- See: [Meeting Playback](features/meeting-playback.md), [Summary & Action Items](features/summary-action-items.md)

## Search Across Meetings

- User navigates to `/search`
- Types a query and submits; the backend lists every `meetings/<id>/summary.json` in B2 and pulls them in parallel along with each meeting's `transcript.json`
- Results show one hit per meeting: title, kind (summary / transcript), server-extracted snippet centered on the match, and a deep link into the meeting
- Empty query renders an empty-state card; zero hits renders an empty-state with the count of meetings searched
- See: [Cross-Meeting Search](features/cross-meeting-search.md)

## Browse the Full Bucket (Files)

- User navigates to `/files`
- Page loads file list from `GET /files` (sorted most recent first)
- Files displayed in tree view with folders and type-specific icons
- Top-level folders auto-expand on load — `meetings/` and `uploads/` are immediately visible
- Hover a file row to see action buttons (preview / download / delete)
- **Preview**: opens dialog with image/PDF preview + metadata panel for non-meeting content
- **Download**: fetches presigned URL, browser downloads file
- **Delete**: removes file from B2, row removed from tree, toast confirms. To delete an entire meeting bundle, use the `/meetings` page (one DELETE cascades the whole prefix).
- **Bulk delete**: per-row and per-folder checkboxes (folder shows an indeterminate state when only some descendants are selected) — select files and use the header **Delete** to `POST /files/bulk-delete`; toast reports full / partial / total failure
- Empty bucket shows "This bucket is empty" with upload prompt
- See: [Bucket Explorer](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Header offers two actions: a primary **Upload recording** CTA and a secondary **Browse meetings** link
- Empty state: when the bucket holds no meetings, the page collapses to a single hero card ("No meetings yet — upload your first recording") with the upload CTA. The grid below is hidden until the first meeting lands
- With meetings present, the dashboard loads in parallel: stats, recent meetings, upload activity
- **Stats tiles**: meetings count, total transcribed minutes, open action items, uploads today
- **Pipeline state card**: compact chips showing per-state counts (e.g. `Done 12 · Transcribing 1`), sorted by count desc; hidden when there are no meetings
- **Upload activity chart**: last 7 days as a bar chart with a segmented **Uploads / Minutes** toggle — "Uploads" plots meetings per day, "Minutes" plots minutes added per day (sourced from `transcript.duration_ms` when present)
- **Recent meetings table**: last 10 meetings with columns Meeting / State / Date / Open. The Open action navigates to the detail page
- See: [Dashboard](features/dashboard.md)
