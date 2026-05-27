<!-- last_verified: 2026-05-27 -->
# Reliability

Reliability expectations and practices for the AI Meeting Notes sample.

## Health Checks

- `GET /health` verifies B2 connectivity and returns `healthy` or `degraded`
- Health endpoint is always available, even when B2 is down

## Error Handling

- HTTP handlers return structured error responses with appropriate status codes
- External service failures (B2, transcription provider, LLM) are caught at the repo boundary and either raised as `RuntimeError` / `TranscriptionError` / `LLMError` for the service layer to handle, or surfaced as 5xx responses to the client
- No unhandled exceptions leak stack traces to clients

## Pipeline Failure Modes

The meeting pipeline runs in three stages (ASR -> summary -> actions). Each stage is independent and writes its artifact (`transcript.json` / `summary.json` / `actions.json`) to B2 before advancing.

| Failure | Behavior |
|---------|----------|
| Transcription provider 4xx / missing key / SDK error | Stage marked `failed` in `status.json` with error message; later stages skipped; `recording.<ext>` remains in B2 |
| Transcription provider 5xx / timeout | Same as above — no automatic retry in v1; user can DELETE the meeting and re-upload |
| LLM 4xx (e.g., bad key) | Summary or actions stage marked `failed`; the meeting still has a transcript |
| Transcript decoded but empty | Summary stage returns a literal "Empty transcript" stub; actions stage returns an empty list |
| Unexpected in-process exception mid-stage | The currently running stage is marked `failed` and the message is persisted to `status.json` |
| Process crash mid-stage | `status.json` reflects the last written state; the meeting is "stuck" and visible as such on the dashboard |
| B2 read failure on artifact fetch | API surfaces a 5xx; client retries via TanStack Query (`retry: 1`) |
| B2 write failure during stage | Stage marked `failed`; pipeline aborts |

The "partial bundle" case — `recording.<ext>` exists but later artifacts don't — is the *normal* mid-pipeline state. The Meetings list and detail page treat missing artifacts as "not yet available" rather than as errors.

## Retry Strategy

- The pipeline does not retry automatically in v1 — the failure modes above are deliberate dead-letter states the user can see and act on.
- Re-running the pipeline for a `failed` meeting: delete and re-upload. A `POST /meetings/{id}/retry` endpoint is in the tech-debt tracker.
- The multi-instance background-queue migration (Celery / RQ / SQS) is documented under `docs/exec-plans/active/background-queue-migration.md`.

## Logging

- Structured JSON logging via Python stdlib
- Every request gets a `request_id` for tracing
- Every pipeline stage emits start + end log lines with the meeting id, so a stuck meeting is grep-able
- Log levels: ERROR for failures, WARNING for degraded state, INFO for requests + pipeline stages

## Observability

- Request timing middleware logs duration for every request
- `/metrics` endpoint exposes basic Prometheus-format counters
- Upload success/failure counts tracked

## Graceful Degradation

- Meeting listing returns empty list (not error) when B2 has no meetings
- Missing transcript / summary / actions artifacts return 404 (not 500) — the UI shows "not yet available"
- Frontend shows skeleton states while loading, error states on failure
- Search across an empty bucket returns `{ hits: [], meetings_searched: 0 }`

## Deployment

- Railway health checks on `/health`
- Zero-downtime deploys via rolling updates
- Environment-specific configuration via env vars (no config files in prod)
- Provider credentials (AssemblyAI / OpenAI / Anthropic) are deploy-time env vars; rotating them does not require a code change
