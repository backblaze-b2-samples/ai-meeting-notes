<!-- last_verified: 2026-05-26 -->
# Feature: Audio Metadata Extraction

## Purpose
Read duration, sample rate, channels, bit depth, and codec from an uploaded audio recording before it lands in B2. Pure-Python — stdlib `wave` for uncompressed WAV, `mutagen` for everything else. Used in the meeting pipeline as a low-fidelity fallback for duration when transcription has not yet completed; the diarization-aware duration comes from the transcript itself.

## Used By
- Pipeline: indirectly via `service/upload.py::process_meeting_upload` for the legacy `/upload` route
- API: `POST /upload` (legacy alias) returns `FileMetadataDetail` for telemetry / debugging

## Core Functions
- `services/api/app/service/audio_metadata.py` — `extract_metadata()`, `extract_audio_metadata()`, `_extract_wav_metadata()`, `_extract_mutagen_metadata()`, `to_s3_metadata()`, `S3_AUDIO_META_KEYS`

## Canonical Files
- Audio metadata pattern: `services/api/app/service/audio_metadata.py`

## Inputs
- file_data: bytes
- filename: string
- content_type: string

## Outputs
- `FileMetadataDetail`: filename, size_bytes, size_human, mime_type, extension, md5, sha256, uploaded_at
- Audio-specific (populated when `content_type` matches `audio/*`): `duration_ms`, `sample_rate`, `channels`, `bit_depth`, `codec`

## Supported formats
- `.wav` — stdlib `wave` (uncompressed PCM, reported as `codec=wav`); falls back to mutagen for compressed WAV containers
- `.mp3` — mutagen (`MP3`)
- `.flac` — mutagen (`FLAC`)
- `.ogg / .opus` — mutagen (`OggVorbis` / `OggOpus`)
- `.m4a / .aac / .mp4` — mutagen (`MP4`)

## Error modes
- Corrupt audio -> extractor logs a warning, returns `{}`, upload still succeeds with `None` audio fields. We never 500 on a metadata failure.
- Unsupported codec -> mutagen returns `None`; extractor returns `{}`.
- Truncated `.wav` -> stdlib `wave` raises; falls back to mutagen (which may also fail). Result is `{}`.

## Relationship to the meeting pipeline
The canonical source of truth for a meeting's duration is `transcript.json` (`duration_ms`) — populated by the transcription provider after ASR runs. `audio_metadata.py` is retained because it's a cheap pre-pipeline duration estimate and because the legacy `/upload` route still returns a `FileMetadataDetail`. The Dashboard's "Transcribed Time" aggregate reads from transcripts, not from this module.

## Verification
- Test files: extend `services/api/tests/` as needed
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`

## Related Docs
- [Meeting Upload](meeting-upload.md)
- [Summary & Action Items](summary-action-items.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
