<!-- last_verified: 2026-05-27 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Dashboard with meeting-aware stats (total meetings, total transcribed minutes, open action items), upload activity chart, pipeline-state breakdown, recent meetings table
  - **Meetings** (`/meetings`) — `MeetingCard` grid scoped to the `meetings/` prefix; one card per recording with title, state, summary excerpt
  - **Meeting Detail** (`/meetings/<id>`) — synced player + click-to-seek transcript + summary + action-item checklist + live pipeline status (polled)
  - **Upload** (`/upload`) — drag-and-drop with progress tracking; recordings land under `meetings/<id>/recording.<ext>` and the pipeline kicks off as a background task
  - **Search** (`/search`) — cross-meeting substring search over every meeting's summary and transcript; pulls live from B2 on every query
  - **Files** (`/files`) — full B2 bucket explorer (tree view, preview, download, delete) for ops-style browsing
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API for meetings (create / list / get / delete), pipeline status, transcript / summary / actions reads, presigned playback + download, and cross-meeting search
  - B2 S3 integration via boto3 (single cached client with `user_agent_extra="b2ai-ai-meeting-notes"`)
  - Transcription via AssemblyAI (diarized), behind a `repo/transcription.py` adapter
  - LLM via OpenAI (JSON-schema structured outputs, default) or Anthropic Claude (tool-use), selectable with `LLM_PROVIDER`, behind a `repo/llm.py` adapter
  - Pipeline orchestration via FastAPI `BackgroundTasks` — ASR -> summary -> actions
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions mirroring the Pydantic models (`Meeting`, `MeetingStatus`, `Transcript`, `TranscriptSegment`, `SpeakerTurn`, `Summary`, `ActionItem`, `ActionsBundle`, `SearchHit`, `SearchResponse`, `FileMetadata`, …)

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 + AssemblyAI + OpenAI/Anthropic adapters) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3`, `assemblyai`, `openai`, `anthropic` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                          App entrypoint, middleware, router registration
  app/
    types/                         Pydantic models
      files.py, formatting.py
      meeting.py                   Meeting, MeetingStatus, Transcript, TranscriptSegment, SpeakerTurn, Summary, ActionItem, ActionsBundle
      search.py                    SearchHit, SearchResponse
      stats.py, upload.py
    config/
      settings.py                  pydantic-settings; reads .env
    repo/                          External SDK boundary
      b2_client.py                 Generic S3 helpers + cached client factory
      meetings_store.py            Per-meeting bundle layout (recording + JSON artifacts) on B2
      transcription.py             AssemblyAI (diarized)
      llm.py                       OpenAI (JSON-schema) or Anthropic Claude (tool-use) — summarize + extract_actions
    service/                       Business logic
      meeting.py                   Listings, validation, presigned URLs, aggregates
      pipeline.py                  ASR -> summary -> actions executor (BackgroundTasks)
      search.py                    Cross-meeting substring search (parallel B2 reads)
      upload.py                    Legacy /upload alias — delegates to init_meeting + pipeline
      files.py                     Bucket explorer (list / preview / download / delete)
      audio_metadata.py            Common audio metadata extractor (still used for duration hints)
    runtime/                       FastAPI route handlers
      meetings.py                  GET/POST/DELETE /meetings, /meetings/{id}/{status,transcript,summary,actions,playback,download}
      search.py                    GET /search?q=
      upload.py                    Legacy POST /upload
      files.py                     GET /files, /files/{key}/{download,preview}, DELETE
      health.py, metrics.py
  tests/                           pytest tests (structural + integration)
```

## Boundary Invariants

- **No external SDK leakage**: `boto3`, `assemblyai`, `openai`, `anthropic` are only imported in `app/repo/`. The service layer consumes provider-neutral dicts and Pydantic models.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models. The repo adapters convert SDK objects into dicts before crossing into service/.
- **No mutable globals**: Configuration is read-only after init.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. Meeting ids validated against `^[A-Za-z0-9_-]{6,64}$` (see `repo/meetings_store.py::MEETING_ID_RE`) with explicit `..` / `/` rejection before any B2 call.
- **Custom user agent**: every `boto3.client("s3", …)` sets `Config(user_agent_extra="b2ai-ai-meeting-notes", signature_version="s3v4")`. No `b2-native` calls.

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repo (see `infra/railway/README.md`)

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - Meeting bundles under `meetings/<id>/{recording.<ext>,status.json,transcript.json,summary.json,actions.json}`
  - Generic uploads under `uploads/<safe-filename>` (kept for compatibility with the underlying starter kit's bucket explorer)
  - No application database — B2 is the sole data store. Search reads `summary.json` and `transcript.json` directly from B2 on every query.

## External Services

- **Backblaze B2 S3 API** — recording + JSON artifact storage, listing, deletion, presigned URLs
- **AssemblyAI** — diarized transcription via the `assemblyai` SDK
- **OpenAI** (default LLM) — summary + action-item extraction via JSON-schema structured outputs
- **Anthropic Claude** (alternative LLM, when `LLM_PROVIDER=anthropic`) — summary + action-item extraction via tool-use

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins
- **API -> B2** — authenticated via application keys, signature v4
- **API -> AssemblyAI / OpenAI / Anthropic** — bearer-token auth, keys live only in the API process env
- **Client -> B2** — presigned URLs for playback (inline) and download (attachment); 10-min expiry

## Data Flows

- **Meeting Upload**: Browser -> `POST /meetings` (multipart) -> API validates -> `service.meeting.init_meeting` writes `recording.<ext>` + `status.json` (state=queued) -> response returns the `Meeting` row -> FastAPI `BackgroundTasks` kicks off `service.pipeline.run_pipeline`
- **Pipeline (background)**: `run_pipeline` -> ASR stage rewrites `status.json` (state=transcribing) -> calls `repo.transcription.transcribe` -> writes `transcript.json` -> summary stage rewrites `status.json` (state=summarizing) -> calls `repo.llm.summarize` -> writes `summary.json` -> actions stage -> calls `repo.llm.extract_actions` -> writes `actions.json` -> final rewrite of `status.json` (state=done). Any failure marks `status.json` with `state=failed, error=<msg>` and aborts the chain.
- **Meeting list**: Browser -> `GET /meetings` -> service lists `meetings/<id>/recording.*` keys -> parallel reads of `status.json` + `summary.json` for each meeting -> shapes `Meeting[]` rows -> returns newest-first
- **Status polling**: Browser -> `GET /meetings/{id}/status` -> reads `status.json`. TanStack Query refetches every 2.5s while the state is non-terminal.
- **Playback**: Browser -> `GET /meetings/{id}/playback` -> service validates id + HEADs recording -> repo presigns inline GET -> browser renders `<audio controls>`
- **Download**: Browser -> `GET /meetings/{id}/download` -> service validates id -> repo presigns GET with `Content-Disposition: attachment` -> browser downloads
- **Delete**: Browser -> `DELETE /meetings/{id}` -> service validates id -> repo lists every key under `meetings/<id>/` -> batch-deletes via S3 DeleteObjects -> TanStack Query invalidates meetings + stats
- **Cross-meeting search**: Browser -> `GET /search?q=...` -> service lists every `summary.json` key -> parallel reads of `summary.json` + `transcript.json` -> case-insensitive substring scan + server-extracted snippet -> returns `SearchResponse`

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)
- Each pipeline stage emits start + end log lines with the meeting id so a stuck pipeline is grep-able

## Canonical Files

- Meeting route handlers: `services/api/app/runtime/meetings.py`
- Meeting service orchestration: `services/api/app/service/meeting.py`
- Pipeline executor: `services/api/app/service/pipeline.py`
- Cross-meeting search: `services/api/app/service/search.py` + `app/runtime/search.py`
- B2 bundle layout (repo): `services/api/app/repo/meetings_store.py`
- B2 generic helpers + cached client (repo): `services/api/app/repo/b2_client.py`
- Transcription adapter (repo): `services/api/app/repo/transcription.py`
- LLM adapter (repo): `services/api/app/repo/llm.py`
- Pydantic models: `services/api/app/types/` (`meeting.py`, `search.py`, `files.py`, `stats.py`, `upload.py`, `formatting.py`)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- TanStack Query hooks (incl. status polling): `apps/web/src/lib/queries.ts`
- Meeting UI: `apps/web/src/components/meetings/{meeting-card,transcript-view,summary-panel,action-items-list,pipeline-status,waveform}.tsx`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Meeting Upload](docs/features/meeting-upload.md)
- [Meetings Library](docs/features/meetings-library.md)
- [Meeting Playback](docs/features/meeting-playback.md)
- [Summary & Action Items](docs/features/summary-action-items.md)
- [Cross-Meeting Search](docs/features/cross-meeting-search.md)
- [Pipeline Status](docs/features/pipeline-status.md)
- [Bucket Explorer](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — pipeline failure modes, retry strategy
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
