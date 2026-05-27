<!-- last_verified: 2026-05-26 -->
# Background Queue Migration (Celery / RQ / SQS)

> Status: **Deferred** — v1 uses FastAPI `BackgroundTasks` (in-process).

## Goal
Move the meeting pipeline off in-process `BackgroundTasks` and onto a
multi-instance queue so:
- The API process can scale horizontally without dropping stage progress
- Stage retries become real (with backoff + dead-letter)
- A worker can be deployed independently (different machine size for the LLM-heavy stages)

## Why v1 uses BackgroundTasks
`BackgroundTasks` is enough for a single-process demo and keeps the deps
small. The pipeline already writes `status.json` between stages, so a
crashed worker leaves a *recoverable* meeting in B2 — the missing piece
is automatic re-queueing.

## Sketch
- Add `repo/queue.py` — a thin adapter over Celery (Redis broker) or RQ.
- `service/pipeline.py::run_pipeline` becomes a queue producer:
  - `_run_asr` -> task `meeting.asr`
  - `_run_summary` -> task `meeting.summary` (depends on asr)
  - `_run_actions` -> task `meeting.actions` (depends on summary)
- Workers live in a new `services/worker/` directory; structural tests
  treat it like the API service (same layered rules).
- The `status.json` stage states map directly onto Celery task states;
  failed tasks rewrite `state=failed` exactly as the BackgroundTasks
  path does today.

## Rough effort
1 week to swap, plus a few days for the deploy + observability work.
