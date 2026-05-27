"""Meeting orchestration: ids, validation, listings, aggregates.

The pipeline runner that does ASR -> summary -> actions lives in
`service/pipeline.py`. This module owns everything else: id minting and
validation, upload bootstrap (write recording + initial status), the
listing shape, presigned URLs, deletion, and the dashboard aggregates.
"""

from __future__ import annotations

import logging
import mimetypes
import re
import uuid

from app.repo import (
    ACTIONS_KEY,
    MEETING_ID_RE,
    STATUS_KEY,
    SUMMARY_KEY,
    TRANSCRIPT_KEY,
    delete_meeting,
    get_artifact,
    get_artifacts_parallel,
    get_presigned_url,
    head_recording,
    list_meetings,
    presign_recording_playback,
    put_recording,
)
from app.service.pipeline import run_pipeline, write_initial_status
from app.types import Meeting
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)


SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    {"wav", "mp3", "flac", "ogg", "oga", "opus", "m4a", "mp4", "aac"}
)
SUPPORTED_VIDEO_EXTENSIONS = frozenset({"mp4", "mov", "webm", "mkv"})
ALL_SUPPORTED = SUPPORTED_AUDIO_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

_SAFE_TITLE_RE = re.compile(r"[^\w\-. ]")

__all__ = [
    "ALL_SUPPORTED",
    "MeetingIdError",
    "MeetingNotFound",
    "aggregate_for_dashboard",
    "get_download_url",
    "get_meeting",
    "get_meeting_actions",
    "get_meeting_status",
    "get_meeting_summary",
    "get_meeting_transcript",
    "get_playback_url",
    "init_meeting",
    "list_meeting_rows",
    "new_meeting_id",
    "remove_meeting",
    "run_pipeline",
    "validate_meeting_id",
]


class MeetingNotFound(Exception):
    """Raised when no meeting exists at the requested id."""

    def __init__(self, detail: str = "Meeting not found"):
        self.detail = detail
        super().__init__(detail)


class MeetingIdError(Exception):
    """Raised when the supplied meeting id is malformed."""

    def __init__(self, detail: str = "Invalid meeting id"):
        self.detail = detail
        super().__init__(detail)


def validate_meeting_id(meeting_id: str) -> None:
    """Reject ids that fail the canonical shape or look like path traversal."""
    if not meeting_id or ".." in meeting_id or "/" in meeting_id:
        raise MeetingIdError()
    if not MEETING_ID_RE.match(meeting_id):
        raise MeetingIdError()


def new_meeting_id() -> str:
    """Mint a new URL-safe meeting id."""
    return uuid.uuid4().hex[:16]


def _ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"


def _title_from_filename(filename: str) -> str:
    """Strip extension + sanitize the filename into a human-readable title."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    cleaned = _SAFE_TITLE_RE.sub(" ", stem).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "Untitled meeting"


def _content_type_for(key: str) -> str:
    mime, _ = mimetypes.guess_type(key)
    return mime or "application/octet-stream"


def _id_from_recording_key(key: str) -> str:
    parts = key.split("/")
    return parts[1] if len(parts) >= 3 else ""


def init_meeting(
    file_data: bytes,
    filename: str,
    content_type: str,
) -> tuple[str, str]:
    """Synchronously persist the recording + initial status. Returns (id, key)."""
    ext = _ext_of(filename)
    if ext not in ALL_SUPPORTED:
        raise MeetingIdError(f"Unsupported recording extension: .{ext}")
    meeting_id = new_meeting_id()
    recording_key_str = put_recording(meeting_id, file_data, ext, content_type)
    write_initial_status(meeting_id)
    title = _title_from_filename(filename)
    logger.info(
        "Meeting initialized: id=%s key=%s title=%s",
        meeting_id,
        recording_key_str,
        title,
    )
    return meeting_id, recording_key_str


def _meeting_from_listing(
    obj: dict, status: dict | None, summary: dict | None
) -> Meeting:
    """Shape a listing row from the recording HEAD + sidecar artifacts.

    Summary excerpt is the first line of the summary, truncated to a
    card-friendly length. State falls back to "queued" when status hasn't
    been written yet (very narrow race after upload).
    """
    key = obj["Key"]
    meeting_id = _id_from_recording_key(key)
    filename = key.rsplit("/", 1)[-1]
    state = (status or {}).get("state") or "queued"
    error = (status or {}).get("error")
    summary_text = (summary or {}).get("summary") if summary else None
    excerpt = None
    if summary_text:
        excerpt = summary_text.strip().split("\n", 1)[0][:240]
    return Meeting(
        meeting_id=meeting_id,
        recording_key=key,
        filename=filename,
        size_bytes=obj["Size"],
        size_human=humanize_bytes(obj["Size"]),
        content_type=_content_type_for(key),
        created_at=obj["LastModified"],
        duration_ms=None,
        speaker_count=None,
        summary_excerpt=excerpt,
        state=state,
        error=error,
    )


def list_meeting_rows(limit: int = 100) -> list[Meeting]:
    """List meetings newest-first, one row per recording.

    Reads each meeting's `status.json` + `summary.json` in parallel so
    the card shows current state and an excerpt. Missing artifacts leave
    those fields unset (the row still lists).
    """
    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500")
    raw = list_meetings(max_keys=1000)
    raw.sort(key=lambda o: o["LastModified"], reverse=True)
    raw = raw[:limit]
    ids = [_id_from_recording_key(o["Key"]) for o in raw]
    statuses = get_artifacts_parallel(ids, STATUS_KEY)
    summaries = get_artifacts_parallel(ids, SUMMARY_KEY)
    return [
        _meeting_from_listing(
            obj,
            statuses.get(_id_from_recording_key(obj["Key"])),
            summaries.get(_id_from_recording_key(obj["Key"])),
        )
        for obj in raw
    ]


def get_meeting(meeting_id: str) -> Meeting:
    validate_meeting_id(meeting_id)
    head = head_recording(meeting_id)
    if head is None:
        raise MeetingNotFound()
    status = get_artifact(meeting_id, STATUS_KEY)
    summary = get_artifact(meeting_id, SUMMARY_KEY)
    return _meeting_from_listing(head, status, summary)


def get_meeting_status(meeting_id: str) -> dict | None:
    validate_meeting_id(meeting_id)
    return get_artifact(meeting_id, STATUS_KEY)


def get_meeting_transcript(meeting_id: str) -> dict | None:
    validate_meeting_id(meeting_id)
    return get_artifact(meeting_id, TRANSCRIPT_KEY)


def get_meeting_summary(meeting_id: str) -> dict | None:
    validate_meeting_id(meeting_id)
    return get_artifact(meeting_id, SUMMARY_KEY)


def get_meeting_actions(meeting_id: str) -> dict | None:
    validate_meeting_id(meeting_id)
    return get_artifact(meeting_id, ACTIONS_KEY)


def get_playback_url(meeting_id: str) -> str:
    """Inline-playback presigned URL (no Content-Disposition)."""
    validate_meeting_id(meeting_id)
    head = head_recording(meeting_id)
    if head is None:
        raise MeetingNotFound()
    return presign_recording_playback(head["Key"])


def get_download_url(meeting_id: str) -> str:
    """Download presign with `Content-Disposition: attachment`."""
    validate_meeting_id(meeting_id)
    head = head_recording(meeting_id)
    if head is None:
        raise MeetingNotFound()
    filename = head["Key"].rsplit("/", 1)[-1]
    return get_presigned_url(head["Key"], filename=filename)


def remove_meeting(meeting_id: str) -> tuple[list[str], list[dict]]:
    """Cascade-delete every object under the meeting's prefix."""
    validate_meeting_id(meeting_id)
    return delete_meeting(meeting_id)


def aggregate_for_dashboard() -> dict:
    """Meeting-centric aggregates for the dashboard endpoint.

    Reads `status.json`, `transcript.json` (for duration), and
    `actions.json` (for open-actions count) for every meeting in
    parallel. Missing artifacts contribute to `meetings_by_state` but
    not to duration / actions totals.
    """
    raw = list_meetings(max_keys=10_000)
    ids = [_id_from_recording_key(o["Key"]) for o in raw]
    statuses = get_artifacts_parallel(ids, STATUS_KEY)
    transcripts = get_artifacts_parallel(ids, TRANSCRIPT_KEY)
    actions = get_artifacts_parallel(ids, ACTIONS_KEY)

    total_size = sum(o["Size"] for o in raw)
    total_duration = 0
    by_state: dict[str, int] = {}
    open_actions = 0
    for mid in ids:
        st = statuses.get(mid) or {}
        state = st.get("state", "queued")
        by_state[state] = by_state.get(state, 0) + 1
        tr = transcripts.get(mid) or {}
        dur = tr.get("duration_ms")
        if isinstance(dur, int):
            total_duration += dur
        ac = actions.get(mid) or {}
        for item in ac.get("items") or []:
            if item.get("status", "open") == "open":
                open_actions += 1
    return {
        "total_meetings": len(raw),
        "total_duration_ms": total_duration,
        "meetings_size_bytes": total_size,
        "meetings_size_human": humanize_bytes(total_size),
        "open_action_items": open_actions,
        "meetings_by_state": by_state,
    }
