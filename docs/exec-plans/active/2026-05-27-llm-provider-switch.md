<!-- last_verified: 2026-05-27 -->
# LLM provider switch (Anthropic ↔ OpenAI) + AssemblyAI-only transcription

> Status: **In progress.** Move to `completed/` after the verification steps in §4 pass on a real run.

## Goal
Make summary + action-item extraction provider-pluggable behind `LLM_PROVIDER` (OpenAI default, Anthropic Claude alternative), and remove the OpenAI Whisper transcription path so the sample always demonstrates diarized output. Net result for the user: two API keys total — AssemblyAI + OpenAI — both extremely common.

## Why now
- The sample exists in part to show diarized transcripts. The OpenAI Whisper alternative silently fell back to a single `Speaker 1` for the whole recording — present but actively hurting the demo when picked.
- Anthropic-only LLM raised the bar for first-time setup. Defaulting to OpenAI (and pairing it with AssemblyAI for transcription) keeps onboarding to two well-known providers; Anthropic Claude is still available with a single env-var flip.
- `OPENAI_API_KEY` is already in `.env.example`; we reclaim it for the LLM role exclusively, so no new top-level env semantics.

## Decisions
- **OpenAI structured-output mechanism**: `response_format: {type: "json_schema", strict: true}` (not function calling). Default model `gpt-4o-mini`.
- **Shared schema**: `SUMMARY_SCHEMA` / `ACTIONS_SCHEMA` are defined once in `repo/llm.py` and reused by both providers. OpenAI strict mode requires `additionalProperties: false` and every property in `required`; optional fields are expressed as `["string", "null"]`. Anthropic tool-use accepts the same schema.
- **`transcribe()` signature**: drop the `content_type` parameter — only the removed OpenAI Whisper path used it. The change ripples through `_run_asr`, `run_pipeline`, and the two `BackgroundTasks.add_task(run_pipeline, …)` call sites.
- **`MeetingStatus.transcription_provider`**: kept (now always `"assemblyai"`), still informational.

## Touch list

Code:
- `services/api/app/repo/llm.py` (rewrite)
- `services/api/app/repo/transcription.py` (drop OpenAI branch + dispatch)
- `services/api/app/service/pipeline.py` (drop `content_type` in `_run_asr`, `run_pipeline`)
- `services/api/app/runtime/upload.py` (drop `content_type` in `run_pipeline` call)
- `services/api/app/runtime/meetings.py` (drop `content_type` in `run_pipeline` call)
- `services/api/tests/test_llm.py` (new)
- `scripts/doctor.mjs` (preflight: require `ASSEMBLYAI_API_KEY`; gate Anthropic vs OpenAI on `LLM_PROVIDER`)

Config / docs:
- `.env.example`
- `README.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `infra/railway/README.md`
- `docs/features/summary-action-items.md`
- `docs/features/meeting-upload.md`
- `docs/dev-workflows.md` (replaces "Adding a transcription provider" with "Adding an LLM provider")
- `docs/SECURITY.md` (header bump; trust-boundary line still accurate)

## Verification
1. `pnpm lint:api && pnpm test:api && pnpm check:structure` — clean.
2. `pnpm build` — frontend type-check still happy (shared types unchanged).
3. End-to-end smoke:
   - Default (`LLM_PROVIDER` unset) + valid `OPENAI_API_KEY`: upload a short clip, watch `status.json` progress through asr → summary → actions; `summary.model` starts with `gpt-`.
   - `LLM_PROVIDER=anthropic` + valid `ANTHROPIC_API_KEY`: same flow; `summary.model` starts with `claude-`.
   - `OPENAI_API_KEY` unset (and no `LLM_PROVIDER` override): pipeline fails at the summary stage with `OPENAI_API_KEY is not set` in `status.json.error`.
4. Spot-check `transcript.json` shows multiple `Speaker N` labels (diarization still works after the dispatch removal).

## Done when
- All four verification steps green.
- Plan moved to `docs/exec-plans/completed/`.
