"""Upload service: validate, persist recording, kick the meeting pipeline.

The `/upload` entrypoint is preserved for backwards compatibility with
the underlying starter kit — but in this sample it's a thin alias for
the meeting create flow. Both routes funnel through `init_meeting` so
the B2 layout (`meetings/<id>/...`) stays consistent regardless of which
endpoint the client hits.
"""

from __future__ import annotations

import re

from app.config import settings
from app.service.audio_metadata import AUDIO_MIME_TYPES, extract_metadata
from app.service.meeting import (
    ALL_SUPPORTED,
    MeetingIdError,
    get_meeting,
    init_meeting,
)
from app.types import FileUploadResponse, Meeting
from app.types.formatting import humanize_bytes

ACCEPTED_VIDEO_MIME = frozenset(
    {
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "video/x-matroska",
    }
)
ALLOWED_CONTENT_TYPES = AUDIO_MIME_TYPES | ACCEPTED_VIDEO_MIME

_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename: strip path components, remove unsafe chars, limit length."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = re.sub(r"[_.]{2,}", "_", name)
    name = name.lstrip(".").strip()
    if len(name) > 200:
        base, _, ext = name.rpartition(".")
        name = base[: 200 - len(ext) - 1] + "." + ext if ext else name[:200]
    return name or "unnamed"


class UploadError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def file_too_large_detail() -> str:
    return f"File too large. Max size: {humanize_bytes(settings.max_file_size)}"


def process_meeting_upload(
    file_data: bytes,
    filename: str,
    content_type: str,
    content_length: int | None = None,
) -> tuple[Meeting, FileUploadResponse]:
    """Validate and persist a meeting recording.

    Returns both the `Meeting` row (so callers can return it from
    `POST /meetings`) and a `FileUploadResponse` (so the legacy
    `POST /upload` route can keep its shape). The pipeline kickoff is
    the caller's responsibility — we don't import `BackgroundTasks`
    here to keep the service layer framework-agnostic.
    """
    if not filename:
        raise UploadError("No filename provided")

    if content_length and content_length > settings.max_file_size:
        raise UploadError(
            file_too_large_detail(),
            status_code=413,
        )

    safe_name = sanitize_filename(filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""

    if ext not in ALL_SUPPORTED:
        raise UploadError(
            f"Unsupported recording extension '.{ext}'", status_code=415
        )

    is_audio = content_type in AUDIO_MIME_TYPES or content_type.startswith("audio/")
    is_video = content_type in ACCEPTED_VIDEO_MIME or content_type.startswith("video/")
    if not (is_audio or is_video):
        raise UploadError(
            f"Unsupported content type '{content_type}'", status_code=415
        )

    if len(file_data) == 0:
        raise UploadError("Empty file")
    if len(file_data) > settings.max_file_size:
        raise UploadError(
            file_too_large_detail(),
            status_code=413,
        )

    try:
        meeting_id, key = init_meeting(file_data, safe_name, content_type)
    except MeetingIdError as e:
        raise UploadError(e.detail, status_code=415) from None
    except RuntimeError as e:
        raise UploadError(str(e), status_code=502) from None

    meeting = get_meeting(meeting_id)
    detail = extract_metadata(file_data, safe_name, content_type) if is_audio else None
    response = FileUploadResponse(
        key=key,
        filename=safe_name,
        size_bytes=len(file_data),
        size_human=humanize_bytes(len(file_data)),
        content_type=content_type,
        uploaded_at=meeting.created_at,
        url=None,
        metadata=detail,
    )
    return meeting, response
