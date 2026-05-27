<!-- last_verified: 2026-05-26 -->
# AGENTS.md

This is the authoritative control surface for all coding agents on the
**AI Meeting Notes** sample. Read this first.

## 1. Repository Map

```
apps/web/                                  Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  src/app/meetings/                        /meetings — meeting grid (sample-specific)
  src/app/meetings/[id]/                   /meetings/<id> — synced player + transcript + summary + actions
  src/app/search/                          /search   — cross-meeting search
  src/app/upload/                          /upload   — drag-and-drop meeting recording upload
  src/app/files/                           /files    — full-bucket explorer (kept from starter)
  src/components/meetings/                 meeting-card, transcript-view, summary-panel, action-items-list, pipeline-status, waveform
services/api/                              FastAPI backend (layered: types/config/repo/service/runtime)
  app/runtime/meetings.py                  /meetings + /meetings/{id}/{status,transcript,summary,actions,playback,download}
  app/runtime/search.py                    /search
  app/runtime/upload.py                    /upload (legacy alias — delegates to the pipeline)
  app/runtime/files.py                     /files (full-bucket explorer)
  app/service/meeting.py                   Meeting id minting + validation, listings, presigned URLs, aggregates
  app/service/pipeline.py                  ASR -> summary -> actions executor (FastAPI BackgroundTasks)
  app/service/search.py                    Cross-meeting substring search (parallel B2 reads)
  app/service/upload.py                    Legacy upload alias
  app/service/files.py                     Bucket explorer service
  app/repo/meetings_store.py               B2 per-meeting bundle layout (recording + JSON artifacts)
  app/repo/b2_client.py                    boto3 — generic helpers + cached client factory
  app/repo/transcription.py                AssemblyAI transcription adapter (diarized)
  app/repo/llm.py                          Summary + action-item extraction — OpenAI (default) / Anthropic via LLM_PROVIDER
  app/types/meeting.py                     Meeting, MeetingStatus, Transcript, SpeakerTurn, Summary, ActionItem, ActionsBundle
  app/types/search.py                      SearchHit, SearchResponse
packages/shared/                           Shared TypeScript types (Meeting, Transcript, Summary, ActionItem, SearchHit, …)
docs/                                      System of record (features, workflows, security, reliability)
docs/exec-plans/                           Execution plans and tech debt tracker
infra/railway/                             Deployment config
```

## 2. Architectural Invariants

**Backend layering**: `types` -> `config` -> `repo` -> `service` -> `runtime`

- No backward imports across layers
- No `boto3` outside `repo/`
- No `assemblyai`, `openai`, or `anthropic` outside `repo/`
- No business logic in route handlers (`runtime/`)
- All external APIs wrapped in `repo/` adapters
- All request/response data validated at boundary (Pydantic models)
- No shared mutable state across layers

**Frontend**: shadcn/ui components in `src/components/ui/` are generated — never modify them.

**Data fetching**: every API call flows through TanStack Query hooks in `apps/web/src/lib/queries.ts`. No bare `useEffect + fetch` patterns. New endpoints touch three files: `runtime/<router>.py`, `lib/api-client.ts`, `lib/queries.ts`. Status polling lives in `useMeetingStatus` — `refetchInterval` returns `false` once the pipeline reaches a terminal state.

**B2 bundle layout**: every meeting lives under `meetings/<meeting-id>/`, containing exactly `recording.<ext>`, `status.json`, `transcript.json`, `summary.json`, and `actions.json`. Meeting ids match `^[A-Za-z0-9_-]{6,64}$` (see `repo/meetings_store.py::MEETING_ID_RE`); `..` / `/` are explicitly rejected at the service boundary before any B2 call. The full-bucket explorer at `/files` is the secondary surface — it shows the per-meeting bundles next to anything else in the bucket.

**B2 surface**: S3-only. No `b2-native` calls anywhere. Every `boto3.client("s3", …)` instantiation MUST pass `Config(user_agent_extra="b2ai-ai-meeting-notes", signature_version="s3v4")`. No hardcoded region strings in source (use `B2_REGION` from `.env`).

**Pipeline state**: `status.json` is the source of truth. Each pipeline stage rewrites it *before* doing its work, so a UI poll right after upload always finds something and progress is observable without reading the large transcript.

## 3. Quality Expectations

- **DRY** — do not duplicate logic, types, or constants. Extract shared code only when used in 2+ places.
- Structured JSON logging only — no `print()` statements
- No raw SDK calls outside `repo/` layer
- Files stay under 300 lines
- Tests added or updated for every behavior change
- Docs updated in same PR as code changes
- Lint clean before merge
- Prefer boring, composable libraries over clever abstractions
- No implicit type assumptions — use typed models

## 4. Mechanical Enforcement

| Rule | Enforced by |
|------|-------------|
| No backward imports | `tests/test_structure.py::test_no_backward_imports` |
| No boto3 outside repo/ | `tests/test_structure.py::test_boto3_only_in_repo` |
| No transcription/LLM SDKs outside repo/ | `tests/test_structure.py::test_external_sdks_only_in_repo` |
| File size < 300 lines | `tests/test_structure.py::test_file_size_limits` |
| All layers exist | `tests/test_structure.py::test_all_layers_exist` |
| Meeting pipeline modules in place | `tests/test_structure.py::test_required_meeting_modules_exist` |
| No bare print() | `ruff` rule T20 |
| Import ordering | `ruff` rule I001 |
| Frontend strict equality | `eslint` rule eqeqeq |
| No unused vars | `eslint` + `ruff` rules |

## 5. Commands

```bash
# Run
pnpm dev               # start both frontend and backend
pnpm dev:web           # frontend only
pnpm dev:api           # backend only

# Test & Lint
pnpm lint              # frontend lint (eslint)
pnpm build             # frontend type check + build
pnpm lint:api          # backend lint (ruff)
pnpm test:api          # backend tests (pytest)
pnpm check:structure   # structural boundary tests
pnpm test:e2e          # Playwright e2e tests
```

## 6. Agent Workflow

1. Read this file first.
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) before structural changes.
3. For non-trivial changes, create a plan in `docs/exec-plans/active/`.
4. Implement the smallest coherent change.
5. Run: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
6. Update docs in the same PR (see §8).
7. Move completed plans to `docs/exec-plans/completed/`.
8. Only change files relevant to the task. No drive-by improvements.

## 7. Frontend Conventions

See [docs/dev-workflows.md](docs/dev-workflows.md) for full details.

## 8. Doc Update Mapping

| Change Type | Update Location |
|-------------|-----------------|
| Feature logic, inputs, outputs, tests | `docs/features/<feature>.md` |
| User journeys | `docs/app-workflows.md` |
| System layout, deployments | `ARCHITECTURE.md` |
| Dev or testing process | `docs/dev-workflows.md` |
| Setup or scope changes | `README.md` |
| Security changes | `docs/SECURITY.md` |
| Reliability changes | `docs/RELIABILITY.md` |
| Active work plans | `docs/exec-plans/active/` |
| Known tech debt | `docs/exec-plans/tech-debt-tracker.md` |

If documentation and implementation conflict, update docs in the same PR. Documentation rot destroys agent reliability.

## 9. Doc Map

| Topic | Location |
|-------|----------|
| System layout, data flows, boundaries | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Meeting upload | [docs/features/meeting-upload.md](docs/features/meeting-upload.md) |
| Meetings library | [docs/features/meetings-library.md](docs/features/meetings-library.md) |
| Playback + transcript | [docs/features/meeting-playback.md](docs/features/meeting-playback.md) |
| Summary + action items | [docs/features/summary-action-items.md](docs/features/summary-action-items.md) |
| Cross-meeting search | [docs/features/cross-meeting-search.md](docs/features/cross-meeting-search.md) |
| Pipeline status | [docs/features/pipeline-status.md](docs/features/pipeline-status.md) |
| Bucket explorer | [docs/features/file-browser.md](docs/features/file-browser.md) |
| Dashboard | [docs/features/dashboard.md](docs/features/dashboard.md) |
| User journeys | [docs/app-workflows.md](docs/app-workflows.md) |
| Engineering workflows and testing | [docs/dev-workflows.md](docs/dev-workflows.md) |
| Security principles | [docs/SECURITY.md](docs/SECURITY.md) |
| Reliability expectations | [docs/RELIABILITY.md](docs/RELIABILITY.md) |
| Execution plans | [docs/exec-plans/](docs/exec-plans/) |
| Tech debt | [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) |

## 10. When Unsure

- Prefer boring, stable libraries
- Prefer small PRs over large changes
- Add tests with every change
- Never bypass lint rules without explicit instruction
- Ask before making destructive or irreversible changes
