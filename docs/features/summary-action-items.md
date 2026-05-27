<!-- last_verified: 2026-05-27 -->
# Feature: Summary & Action Items

## Purpose
Produce a structured summary, list of decisions, topic chips, and an extracted action-item list for each meeting — stored as JSON artifacts alongside the recording in B2.

## Used By
- UI: `/meetings/<id>` (summary panel + action items list)
- API:
  - `GET /meetings/{id}/summary`
  - `GET /meetings/{id}/actions`
- Job: pipeline stages in `service/pipeline.py`

## Core Functions
- `repo/llm.py::summarize` — returns `{summary, decisions, topics, model}`
- `repo/llm.py::extract_actions` — returns `{items: [...]}`
- `service/pipeline.py::_run_summary` / `_run_actions`

Both functions share a single JSON Schema per output (`SUMMARY_SCHEMA`, `ACTIONS_SCHEMA`) reused by:
- OpenAI via `response_format={"type":"json_schema","strict":true}` (default)
- Anthropic Claude via tool-use (`tool_choice` forces the named tool)

## Canonical Files
- Pattern exemplar: `services/api/app/repo/llm.py` (shared schema + per-provider call helpers + dispatch)

## Inputs
- `transcript`: dict (provider-neutral shape from `repo/transcription.py`)
- Env:
  - `LLM_PROVIDER` — `openai` (default) or `anthropic`
  - When `LLM_PROVIDER=openai`: `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`)
  - When `LLM_PROVIDER=anthropic`: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-haiku-4-5-20251001`)

## Outputs
- `summary.json`: `{ meeting_id, summary, decisions[], topics[], model, generated_at }`
- `actions.json`: `{ meeting_id, items[], model, generated_at }` where each item is `{ id, text, owner?, due?, status, source_segment_ids[] }`

## Flow
1. ASR stage completes, transcript is on B2
2. Summary stage rewrites `status.json` to `state=summarizing` then calls `summarize(transcript_dict)`
3. The structured-output call returns arguments matching `SUMMARY_SCHEMA`; service wraps them in a `Summary` Pydantic model and writes `summary.json`
4. Actions stage runs `extract_actions(transcript_dict)`; for each item, `_segment_ids_for(text, transcript)` performs a cheap substring overlap to seed `source_segment_ids` for the UI's "Source" jump-link
5. Status updates to `state=done`

## Edge Cases
- Empty transcript -> summary returns a literal "Empty transcript" stub; actions returns `[]`
- Missing key for the selected provider (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) -> stage marked `failed` with the env-error message; user sees a red badge on the meeting card
- Provider 5xx or malformed response -> stage marked `failed`, error in `status.json`; no automatic retry in v1
- Transcript too long -> first `MAX_TRANSCRIPT_CHARS` chars are kept, the rest truncated with a marker (logged + documented in `docs/RELIABILITY.md`)

## UX States
- Pipeline still running -> summary panel + actions list show skeletons
- Pipeline done, empty results -> "No action items were extracted"
- Pipeline failed -> the meeting detail page shows the error from `status.json`

## Verification
- Test files: `services/api/tests/test_llm.py` (both providers), `services/api/tests/test_meetings.py`, `tests/test_structure.py` (no `anthropic` / `openai` outside `repo/`)
- Required cases: structured-output validation, missing-key behavior, empty-transcript guard, provider switching

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/RELIABILITY.md](../RELIABILITY.md)
