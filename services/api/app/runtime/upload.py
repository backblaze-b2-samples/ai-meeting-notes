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

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_content_length(header: str | None) -> int | None:
    if header is None:
        return None

    try:
        content_length = int(header)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid Content-Length header",
        ) from None

    if content_length < 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid Content-Length header",
        )
    return content_length


@router.post("/upload", response_model=FileUploadResponse)
async def upload(
    background_tasks: BackgroundTasks, request: Request, file: UploadFile
):
    content_type = file.content_type or "application/octet-stream"
    content_length = _parse_content_length(request.headers.get("content-length"))

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_file_size:
            raise HTTPException(status_code=413, detail="File too large")
        chunks.append(chunk)
    file_data = b"".join(chunks)

    try:
        meeting, response = process_meeting_upload(
            file_data=file_data,
            filename=file.filename or "",
            content_type=content_type,
            content_length=content_length,
        )
    except UploadError as e:
        logger.warning("Upload rejected: %s", e.detail)
        record_upload(success=False)
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None

    background_tasks.add_task(run_pipeline, meeting.meeting_id, file_data)
    record_upload(success=True)
    logger.info(
        "Meeting upload (legacy /upload): id=%s size=%d type=%s",
        meeting.meeting_id,
        response.size_bytes,
        response.content_type,
    )
    return response
