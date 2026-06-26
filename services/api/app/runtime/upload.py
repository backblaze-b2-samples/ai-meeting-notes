"""Legacy `/upload` entrypoint — alias for the meetings create flow.

Kept for compatibility with clients that POSTed to `/upload` on the
underlying starter kit. New clients should hit `POST /meetings`
directly. Both paths use the same service layer and write into the
canonical `meetings/<id>/...` layout.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile

from app.config import settings
from app.runtime.metrics import record_upload
from app.service.meeting import run_pipeline
from app.service.upload import UploadError, process_meeting_upload
from app.types import FileUploadResponse
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


INVALID_CONTENT_LENGTH = "Invalid Content-Length header"


def _file_too_large_error() -> UploadError:
    return UploadError(
        f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
        status_code=413,
    )


def _content_length_exceeds_max(header: str) -> bool:
    normalized = header.lstrip("0") or "0"
    max_size = str(settings.max_file_size)
    return len(normalized) > len(max_size) or (
        len(normalized) == len(max_size) and normalized > max_size
    )


def _parse_content_length(header: str | None) -> int | None:
    if header is None:
        return None

    if not header.isascii() or not header.isdigit():
        raise UploadError(INVALID_CONTENT_LENGTH)

    normalized = header.lstrip("0") or "0"
    if _content_length_exceeds_max(normalized):
        raise _file_too_large_error()

    return int(normalized)


def _reject_upload(error: UploadError) -> None:
    logger.warning("Upload rejected: %s", error.detail)
    record_upload(success=False)
    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    ) from None


@router.post("/upload", response_model=FileUploadResponse)
async def upload(
    background_tasks: BackgroundTasks, request: Request, file: UploadFile
):
    content_type = file.content_type or "application/octet-stream"
    try:
        content_length = _parse_content_length(request.headers.get("content-length"))

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_file_size:
                raise _file_too_large_error()
            chunks.append(chunk)
        file_data = b"".join(chunks)

        meeting, response = process_meeting_upload(
            file_data=file_data,
            filename=file.filename or "",
            content_type=content_type,
            content_length=content_length,
        )
    except UploadError as e:
        _reject_upload(e)

    background_tasks.add_task(run_pipeline, meeting.meeting_id, file_data)
    record_upload(success=True)
    logger.info(
        "Meeting upload (legacy /upload): id=%s size=%d type=%s",
        meeting.meeting_id,
        response.size_bytes,
        response.content_type,
    )
    return response
