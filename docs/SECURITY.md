<!-- last_verified: 2026-05-27 -->
# Security

Security principles and implementation for the AI Meeting Notes sample.

## Trust Boundaries

- **Frontend -> API**: CORS-restricted to configured origins, scoped to `GET/POST/DELETE/OPTIONS`
- **API -> B2**: Authenticated via `B2_APPLICATION_KEY_ID` + `B2_APPLICATION_KEY`, signature v4
- **API -> AssemblyAI / OpenAI / Anthropic**: Bearer-token auth, keys held only in the API process env — never proxied to the client
- **Client -> B2**: Presigned URLs for playback (inline) and download (`Content-Disposition: attachment`), 10-min expiry

## Upload Validation

- Filename sanitization: path traversal, null bytes, unsafe chars stripped
- Extension allowlist (`.wav .mp3 .flac .ogg .m4a .aac .opus .mp4 .mov .webm`)
- Content-type allowlist (audio/* and a small set of video MIME types)
- Chunked streaming with size enforcement (100MB default)
- Empty file rejection

## Meeting ID Validation

- Meeting ids must match `^[A-Za-z0-9_-]{6,64}$` (`repo/meetings_store.py::MEETING_ID_RE`)
- `..` and `/` are explicitly rejected at the service boundary before any B2 call
- IDs are minted server-side via `uuid.uuid4().hex[:16]`; clients never supply ids on create

## File Key Validation (bucket explorer)

- Empty keys rejected
- Path traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- The bucket is the only access boundary — add prefix scoping in
  `services/api/app/service/files.py::validate_key` if your deployment
  shares a bucket with other workloads

## Download Safety

- Bucket-explorer downloads force `Content-Disposition: attachment` (XSS mitigation for arbitrary uploads)
- Meeting playback uses inline disposition so the browser can render `<audio controls>` directly. Recordings under `meetings/<id>/recording.*` are always trusted because they were validated on upload.

## Provider Credential Handling

- All transcription + LLM keys are loaded from environment variables at API process start; the doctor preflight warns when one is missing
- Keys are never written to disk, never logged, and never returned to the client
- Transcription bytes are streamed to the provider in-memory; no temp files persist
- If a stage fails because of a provider 4xx (missing or invalid key), the failure message is stored in `status.json` for the affected meeting only — the rest of the bucket is unaffected

## Secrets Management

- All secrets loaded via environment variables (pydantic-settings + `python-dotenv`)
- Never committed to source control
- `.env.example` documents required variables without values

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never weaken validation without explicit instruction
- Never bypass CORS, auth, or input sanitization
- Always validate at system boundaries
