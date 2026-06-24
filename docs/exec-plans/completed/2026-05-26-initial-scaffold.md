# Scaffold plan — `ai-meeting-notes`

> **Source of truth for this build:** the freshly-cloned tree at
> `.claude/scratch/<source-tree>/`. The user
> overrode the default `vibe-coding-starter-kit` with
> **`ai-audio-starter-kit`** (`https://github.com/backblaze-b2-samples/ai-audio-starter-kit`),
> because this sample is fundamentally an AI-audio app and that starter
> already ships the audio plumbing this sample would otherwise have to
> rebuild.

---

## 1. Purpose

`ai-meeting-notes` is a Backblaze B2 sample that demonstrates a complete
"AI meeting" pipeline end-to-end: a user uploads a meeting recording →
the backend runs diarized speech-to-text → an LLM produces a structured
summary, list of decisions, and extracted action items → every artifact
(recording, transcript, summary, actions, pipeline status) is stored
together under a per-meeting prefix in B2 → the user gets a per-meeting
page with click-to-seek transcript, summary, and an actionable checklist,
plus a **cross-meeting search** that pulls summaries and transcripts
straight out of B2 on every query.

**Audience.** Enterprise + prosumer developers searching for "AI meeting
notes / Otter alternative / Fathom alternative" who want a working
reference architecture for storing meeting bundles on B2. Pipeline is
deliberately swappable (Whisper / AssemblyAI / Claude) — the load-bearing
part of the demo is **B2 as the system of record for unbounded meeting
history with heavy read traffic on search**.

**Why this is a good B2 demo.**
- Each meeting accumulates a recording + 3 JSON artifacts that live in B2
  indefinitely — natural "growing bucket" story.
- Cross-meeting search reads many `summary.json` blobs per query —
  exercises the B2 read path heavily, the dimension B2 is priced to win on.
- The full-bucket explorer (kept from the starter) shows the *physical*
  storage layout next to the *semantic* meeting view — a useful demo of
  what's actually on disk in B2.

---

## 2. Architecture delta from `ai-audio-starter-kit`

The starter kit is unusually well-suited to this sample — it already
ships audio upload, an audio-scoped Library, presigned playback, layered
FastAPI, the full-bucket explorer, custom `user_agent_extra`, B2_* env
vars, and structural enforcement tests. The delta is **mostly additive**:
we layer a meeting pipeline + bundle model on top of the existing audio
plumbing rather than rebuild it.

### Keep (as-is or near-as-is)

| Area | Notes |
|------|-------|
| `services/api/app/{types,config,repo,service,runtime}/` layering | All architectural invariants preserved |
| `repo/b2_client.py` | Generic S3 helpers — only the `user_agent_extra` string changes |
| `repo/b2_audio.py` (parallel HEAD helper) | Reused under new naming for parallel meeting-artifact HEADs |
| `service/audio_metadata.py` | Still useful — duration / sample rate / codec extracted on upload |
| `service/upload.py`, `runtime/upload.py` | Upload entrypoint kept; service hooks now trigger the transcription pipeline |
| `runtime/files.py` + `apps/web/src/app/files/` (**full-bucket explorer**) | **NON-NEGOTIABLE KEEP** per skill — preserved verbatim except for rename strings |
| `runtime/health.py`, `runtime/metrics.py` | General infrastructure, unchanged |
| `apps/web/src/app/upload/` | Drag-and-drop UI kept; copy changed to "Upload a meeting recording" |
| Dashboard surface (`/`) | Page layout kept; stats repurposed to meeting-centric (meetings count, total transcribed minutes, open action items, recent meetings) |
| `apps/web/src/app/design/`, `apps/web/src/app/settings/` | Kept as-is (with rename strings) |
| Theme, error boundaries, loading states, design tokens | Unchanged |
| `scripts/doctor.mjs`, `scripts/dev.sh` | Preflight tooling unchanged |
| Structural tests (`tests/test_structure.py`) | Unchanged; just extended to cover the new modules |
| Ruff + ESLint + 300-line rule + DRY rule | All preserved |
| Railway infra (`infra/railway/`) | Kept; service names renamed |
| Doctor preflight (`pnpm doctor`) | Kept; extended to validate transcription + LLM API keys when present |

### Trim (remove from starter)

| Area | Reason |
|------|-------|
| `apps/web/src/components/library/{library-view,audio-asset-card}.tsx` | Replaced by `components/meetings/*` (a meeting card surfaces duration + speakers + summary preview, not raw audio) |
| `apps/web/src/components/library/waveform.tsx` | Kept and **re-homed** under `components/meetings/` — still useful for the meeting playback surface; not deleted |
| `docs/features/audio-library.md` | Replaced by `docs/features/meetings-library.md` |
| Library/audio nav label "Library" | Renamed to "Meetings" |
| Audio-only README narrative | Rewritten around meetings |

### Add (new for `ai-meeting-notes`)

**Backend (`services/api/app/`)**

| Layer | New file | Purpose |
|------|---------|---------|
| `types/` | `meeting.py` | `Meeting`, `MeetingStatus`, `Transcript`, `TranscriptSegment`, `SpeakerTurn`, `Summary`, `ActionItem` Pydantic models |
| `types/` | `search.py` | `SearchHit`, `SearchResponse` |
| `repo/` | `transcription.py` | Provider-agnostic adapter: `transcribe(audio_bytes, content_type) -> Transcript`. Default impl: AssemblyAI (one call → diarized transcript). Alt impl: OpenAI Whisper API (no diarization, single-speaker fallback). Selected via `TRANSCRIPTION_PROVIDER` env. |
| `repo/` | `llm.py` | Anthropic Claude adapter: `summarize(transcript) -> Summary` and `extract_actions(transcript) -> list[ActionItem]`. Structured output via tool-use; validated against Pydantic. |
| `repo/` | `meetings_store.py` | B2 layout for the meeting bundle: write/read `recording.<ext>`, `transcript.json`, `summary.json`, `actions.json`, `status.json` under `meetings/<meeting-id>/`. **Boto3 stays in `repo/`**. |
| `service/` | `meeting.py` | Orchestrates the pipeline: validate upload → assign meeting-id → write recording → mark `queued` → kick BackgroundTask → ASR → summary → actions → mark `done`/`failed`. |
| `service/` | `search.py` | Cross-meeting search: list `meetings/`, fetch each `summary.json` + `transcript.json` (parallel), score against query (v1: case-insensitive substring with snippet extraction; v2 path documented for embedding-based) |
| `runtime/` | `meetings.py` | `GET /meetings`, `GET /meetings/{id}`, `POST /meetings` (multipart upload, returns meeting id + initial status), `DELETE /meetings/{id}` (cascade-deletes all artifacts), `GET /meetings/{id}/transcript`, `GET /meetings/{id}/summary`, `GET /meetings/{id}/actions`, `GET /meetings/{id}/status`, `GET /meetings/{id}/playback`, `GET /meetings/{id}/download` |
| `runtime/` | `search.py` | `GET /search?q=...` |
| `runtime/` | `meetings_status.py` (optional) | Polling endpoint already covers it; SSE deferred — note in tech-debt-tracker |

**Frontend (`apps/web/src/`)**

| Path | Purpose |
|------|---------|
| `app/meetings/page.tsx` | Meeting grid (replaces /library route, same conceptual slot — sample-specific asset explorer scoped to `meetings/` prefix in B2) |
| `app/meetings/[id]/page.tsx` | Meeting detail: synced player + transcript + summary + actions, with live status when pipeline still running |
| `app/search/page.tsx` | Cross-meeting search with snippet results |
| `components/meetings/meeting-card.tsx` | Card primitive: title, duration, speaker count, summary excerpt, status badge |
| `components/meetings/transcript-view.tsx` | Speaker-turn list, click-to-seek, current-segment highlight |
| `components/meetings/summary-panel.tsx` | Summary + decisions |
| `components/meetings/action-items-list.tsx` | Checkbox list, optional owner + due |
| `components/meetings/pipeline-status.tsx` | Stage indicator (queued → transcribing → summarizing → done / failed) |
| `components/meetings/waveform.tsx` | Re-homed from `components/library/` |
| `lib/api-client.ts` | Extended with `meetings.list/get/create/delete`, `transcript`, `summary`, `actions`, `status`, `search` |
| `lib/queries.ts` | TanStack Query hooks for every new endpoint. **Polling** for `status` while pipeline is non-terminal. |
| `components/layout/nav.tsx` | Nav: Dashboard, **Meetings**, Upload, **Search**, Files |
| `app/library/` | Replaced by `app/meetings/` |
| `components/library/` | Replaced by `components/meetings/` |

**Shared types (`packages/shared/`)**

- Mirror new Pydantic models: `Meeting`, `MeetingStatus`, `Transcript`,
  `TranscriptSegment`, `SpeakerTurn`, `Summary`, `ActionItem`,
  `SearchHit`, `SearchResponse`.

**Env vars (`.env.example`)**

Kept from starter:
```
B2_REGION, B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_PUBLIC_URL_BASE
```

Added:
```
# Transcription provider — "assemblyai" (default, has diarization) or "openai"
TRANSCRIPTION_PROVIDER=assemblyai
ASSEMBLYAI_API_KEY=
OPENAI_API_KEY=                       # only used if TRANSCRIPTION_PROVIDER=openai

# LLM for summary + action-item extraction
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

`pnpm doctor` extended to (a) warn if neither `ASSEMBLYAI_API_KEY` nor
`OPENAI_API_KEY` is set, and (b) warn if `ANTHROPIC_API_KEY` is missing,
without hard-failing (so the bucket + upload UI still works for inspection).

### B2 bundle layout

```
meetings/<meeting-id>/
  recording.<ext>        # original upload (audio or video)
  status.json            # {state, stages: {asr, summary, actions}, error?, updated_at}
  transcript.json        # {segments: [{speaker, start, end, text}], language, duration}
  summary.json           # {summary, decisions, topics, generated_at, model}
  actions.json           # [{text, owner?, due?, status, source_segment_ids}]
```

`status.json` is written *first* (state=`queued`) so a UI poll right
after upload always finds *something*. Each pipeline stage rewrites
`status.json` before producing its artifact, so the UI can show progress
without reading the large transcript every poll.

### Pipeline execution model (v1)

- FastAPI `BackgroundTasks` triggered from `POST /meetings`.
- Stage failures are caught, written into `status.json` (`state=failed`,
  `error=<msg>`), and re-attemptable via `POST /meetings/{id}/retry`
  (stretch — at minimum, deletion + re-upload always works).
- Multi-instance queue migration (Celery / RQ / SQS) noted in
  `docs/exec-plans/active/background-queue-migration.md` so the path is
  visible without bloating v1.

---

## 3. B2 surface

All S3-only, via the existing `repo/b2_client.py` boto3 client (no
`b2-native` calls anywhere). The new `repo/meetings_store.py` reuses the
same client.

| S3 op | Where used |
|------|------------|
| `put_object` | Recording upload, transcript / summary / actions / status writes (status rewritten multiple times per meeting) |
| `list_objects_v2` | `/meetings` listing (filter to `recording.*` keys to get one row per meeting), search enumeration of `summary.json` blobs, deletion cascade |
| `get_object` | Read transcript / summary / actions for detail page; read all `summary.json` (and `transcript.json` for snippet matching) per search query |
| `head_object` | Existence checks; `head_meeting_objects_parallel` (renamed from `head_audio_objects_parallel`) for listing performance |
| `delete_object` / `delete_objects` | Cascade delete: list all `meetings/<id>/*` keys and bulk-delete |
| Presigned URL (`generate_presigned_url`) | `/meetings/{id}/playback` (inline, 10-min expiry), `/meetings/{id}/download` (Content-Disposition: attachment) |

**No b2-native usage.** **All `boto3.client("s3", …)` calls go through
the cached factory in `repo/b2_client.py`, which sets
`Config(user_agent_extra="b2ai-ai-meeting-notes (backblaze-b2-samples)", signature_version="s3v4")`**.

---

## 4. Key features (seed for README + `docs/features/`)

1. **Upload & Transcribe** — drag-and-drop a meeting recording (audio
   or video); the backend stores the original in B2 and triggers a
   diarized speech-to-text pipeline. → `docs/features/meeting-upload.md`
2. **Per-Meeting Summary & Action Items** — Claude produces a structured
   summary, decisions list, and action-item list per meeting; every
   artifact is stored alongside the recording in B2.
   → `docs/features/summary-action-items.md`
3. **Synchronized Playback + Transcript** — click any speaker turn in
   the transcript to seek the player; current segment highlights as
   playback advances. → `docs/features/meeting-playback.md`
4. **Cross-Meeting Search** — query across every meeting's summary and
   transcript; demonstrates the B2 read path under load. v1 is exact
   substring + snippet; v2 path for embeddings sketched in the doc.
   → `docs/features/cross-meeting-search.md`
5. **Pipeline Status** — async pipeline state visible per meeting
   (queued / transcribing / summarizing / done / failed), powered by
   `status.json` polls. → `docs/features/pipeline-status.md`
6. **Meetings Library** — sample-specific asset explorer scoped to the
   `meetings/` prefix; the **full-bucket explorer at `/files` stays**
   for ops-level browsing. → `docs/features/meetings-library.md`

---

## 5. Doc transforms

| File | Action |
|------|--------|
| `README.md` | Rewrite top-to-bottom around meetings; preserve Quick Start shape + B2 onboarding steps |
| `ARCHITECTURE.md` | Rewrite around meetings; refresh "Canonical Files" table; add transcription/LLM/search to External Services |
| `AGENTS.md` | Rewrite §1 Repo Map, §2 Invariants (B2 layout: `meetings/<id>/…`), §5 Commands (unchanged set), §8 Doc map (new feature docs); preserve the layered-architecture rules verbatim |
| `docs/app-workflows.md` | Rewrite around meeting upload + viewing + searching journeys |
| `docs/dev-workflows.md` | Add: how to add a transcription provider (`repo/transcription.py` adapter pattern); how to add a new pipeline stage |
| `docs/SECURITY.md` | Add: external-API credential handling (AssemblyAI / OpenAI / Anthropic); presigned-URL playback unchanged |
| `docs/RELIABILITY.md` | Add: pipeline failure modes, partial-bundle handling, retry strategy |
| `docs/design-system.md` | Replace `AudioAssetCard` reference with `MeetingCard`; add transcript-view + action-items primitives |
| `docs/features/audio-library.md` | **Replace** → `docs/features/meetings-library.md` |
| `docs/features/file-upload.md` | **Replace** → `docs/features/meeting-upload.md` |
| `docs/features/audio-playback.md` | **Replace** → `docs/features/meeting-playback.md` |
| `docs/features/audio-metadata.md` | Keep, light edit (still used at upload time) |
| `docs/features/dashboard.md` | Light edit — repurpose metrics |
| `docs/features/file-browser.md` | Keep, only rename strings |
| `docs/features/transcription-pipeline.md` | **New stub** |
| `docs/features/summary-action-items.md` | **New stub** |
| `docs/features/cross-meeting-search.md` | **New stub** |
| `docs/features/pipeline-status.md` | **New stub** |
| `docs/exec-plans/active/background-queue-migration.md` | **New stub** documenting the v1→v2 path for multi-instance queueing |
| `docs/exec-plans/active/embedding-search.md` | **New stub** documenting the search v2 upgrade path |
| `docs/exec-plans/active/live-recording.md` | **New stub** for the deferred MediaRecorder feature |
| `docs/exec-plans/active/calendar-integration.md` | **New stub** for the deferred calendar feature |

`docs/features/_template.md`, `LICENSE`, `pnpm-workspace.yaml` — keep
(rename strings only where they appear).

---

## 6. Rename table

| Kind | From | To |
|------|------|------|
| Repo root / sample dir | `ai-audio-starter-kit` | `ai-meeting-notes` |
| pnpm workspace name (web) | `@ai-audio-starter-kit/web` | `@ai-meeting-notes/web` |
| pnpm workspace name (shared) | `@ai-audio-starter-kit/shared` | `@ai-meeting-notes/shared` |
| Title case in docs / UI | "AI Audio Starter Kit" | "AI Meeting Notes" |
| Tagline | "Build AI audio applications…" | "Record, transcribe, summarize, and search your meetings — stored on Backblaze B2" |
| `user_agent_extra` value | `b2ai-ai-audio-starter-kit` | `b2ai-ai-meeting-notes (backblaze-b2-samples)` |
| UTM `utm_content` query param | `b2ai-ai-audio-starter-kit` | `b2ai-ai-meeting-notes` |
| Railway service slugs in `infra/railway/` | `ai-audio-starter-kit-*` | `ai-meeting-notes-*` |
| Docker image tag references (if any in infra) | `ai-audio-starter-kit:*` | `ai-meeting-notes:*` |
| Frontend nav label | "Library" | "Meetings" |
| Frontend route | `/library` | `/meetings` |
| Pydantic model | `AudioAsset` | `Meeting` *(new model — different shape, not just renamed)* |
| B2 key prefix | `audio/` | `meetings/<id>/` *(different layout — bundle per meeting, not flat per-file)* |
| Default audio key regex in `service/library.py` | `^audio/…\.(wav\|mp3\|…)$` | `^meetings/[A-Za-z0-9_-]+/recording\.[a-z0-9]+$` *(plus separate validation for transcript/summary/actions/status keys)* |
| Repo URL references in README / docs | `backblaze-b2-samples/ai-audio-starter-kit` | `backblaze-b2-samples/ai-meeting-notes` |
| GitHub Actions workflow names (if present) | `*-ai-audio-starter-kit-*` | `*-ai-meeting-notes-*` |
| Test fixture audio asset names | `audio-fixture-*` | `meeting-fixture-*` |

**Spot-check the entire tree** with `rg "ai-audio-starter-kit"` and
`rg "Audio Starter"` post-build — both should return zero hits outside
of the moved exec-plan in `docs/exec-plans/completed/initial-scaffold.md`
(which legitimately mentions the source kit by name).

---

## 7. Recommendations on the user's open questions

| Open question (from skill input) | Recommendation | Rationale |
|------|------|------|
| Live recording (browser MediaRecorder) vs upload-only in v1? | **Upload-only in v1.** Stub follow-up plan in `docs/exec-plans/active/live-recording.md`. | MediaRecorder + mic permissions + chunked upload + tab-close recovery is a meaningful UI subsystem on its own and would crowd out the B2-pipeline story this sample is trying to tell. Upload-only is enough to demonstrate the full B2 + ASR + LLM loop. |
| Calendar integration (auto-attach to events) — v1 or later? | **Later.** Stub follow-up plan in `docs/exec-plans/active/calendar-integration.md`. | OAuth to Google / Microsoft Calendar pulls in a whole auth + token-refresh + provider-quirk subsystem that has nothing to do with B2. Defer cleanly. |
| Transcription backend? *(my add)* | **AssemblyAI by default** (one call → transcript + diarization), OpenAI Whisper API as a documented alternative (transcript only, single-speaker fallback). Pluggable via `TRANSCRIPTION_PROVIDER` env. | Diarization in v1 without dragging in PyTorch/pyannote. Adapter pattern keeps `service/` provider-agnostic. |
| Summary + action-item LLM? *(my add)* | **Anthropic Claude Haiku 4.5** via `ANTHROPIC_API_KEY`, structured output via tool-use. | Cheap, fast, well-suited to short structured outputs. Single LLM dep keeps env surface small. |
| Pipeline execution? *(my add)* | **FastAPI BackgroundTasks** in v1; multi-instance queue migration documented in `docs/exec-plans/active/background-queue-migration.md`. | Adequate for a single-process demo. Real production needs a queue, and the path is documented but not built. |

The user can override any of these when reviewing the plan; everything
above is a recommendation, not a decision.

---

## 8. Out-of-scope (intentional, for clarity)

- Live in-browser recording (MediaRecorder)
- Calendar integration (Google / Microsoft)
- Speaker identification across meetings (i.e., "this voice is Alice")
- Real-time / streaming transcription
- Multi-instance background queue (Celery / RQ / SQS)
- Embedding-based semantic search
- Mobile apps
- User accounts / auth (everything is single-tenant in v1, matching
  the starter kit's posture)

Each gets a stub exec-plan so the path is discoverable.

---

## 9. Build instructions for the b2-sample-builder

1. **Source tree.** Use ONLY
   `.claude/scratch/<source-tree>/`. Do not
   clone again. Do not read any sibling `ai-audio-starter-kit/` checkout.
2. **Strip git history** when copying.
3. **Apply the rename table in §6 globally** before adding new modules,
   so the new modules drop into an already-renamed tree.
4. **Implement the new modules** per §2 "Add", preserving the strict
   layered architecture (`types -> config -> repo -> service -> runtime`)
   and the structural tests.
5. **Extend the structural tests** so they cover the new modules
   (especially: no `boto3` outside `repo/`, transcription/LLM clients
   live in `repo/` only).
6. **Stub feature pages** per §5 — each new feature gets a doc file
   following `docs/features/_template.md`.
7. **Verify parent-CLAUDE.md standards** before commit:
   - S3 API only, no b2-native calls
   - Every `boto3.client("s3", …)` sets
     `user_agent_extra="b2ai-ai-meeting-notes (backblaze-b2-samples)"`
   - All env vars named `B2_*` for B2 config; provider keys live in their
     own `ASSEMBLYAI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
     namespace
8. **Initial git commit:** "Initial scaffold from `ai-audio-starter-kit`
   (per scratch plan)."
9. **Return** a structured summary of: files created, files modified,
   files deleted, deviations from this plan (with justification), and
   any open questions surfaced during the build.
