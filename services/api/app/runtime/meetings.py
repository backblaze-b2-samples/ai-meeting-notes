"""HTTP surface for the meetings pipeline.

Endpoints:

- `GET    /meetings`                       — list rows (newest first)
- `POST   /meetings`                       — upload recording, kick pipeline
- `GET    /meetings/{id}`                  — single-meeting metadata
- `DELETE /meetings/{id}`                  — cascade delete the bundle
- `GET    /meetings/{id}/status`           — pipeline state (polled)
- `GET    /meetings/{id}/transcript`       — full transcript.json
- `GET    /meetings/{id}/summary`          — summary.json
- `GET    /meetings/{id}/actions`          — actions.json
- `GET    /meetings/{id}/playback`         — inline presigned URL
- `GET    /meetings/{id}/download`         — attachment presigned URL

The pipeline kicks off as a FastAPI BackgroundTask after the recording
is durably in B2 — the POST response carries the meeting id and initial
status so the UI can navigate to `/meetings/{id}` and start polling.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from app.config import settings
from app.runtime.metrics import record_upload
from app.service.meeting import (
    ALL_SUPPORTED,
    MeetingIdError,
    MeetingNotFound,
    get_download_url,
    get_meeting,
    get_meeting_actions,
    get_meeting_status,
    get_meeting_summary,
    get_meeting_transcript,
    get_playback_url,
    init_meeting,
    list_meeting_rows,
    remove_meeting,
    run_pipeline,
)
from app.types import (
    ActionsBundle,
    Meeting,
    MeetingStatus,
    Summary,
    Transcript,
)
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/meetings", response_model=list[Meeting])
async def list_meetings_endpoint(limit: int = 100):
    try:
        return list_meeting_rows(limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/meetings", response_model=Meeting)
async def create_meeting_endpoint(
    background_tasks: BackgroundTasks, file: UploadFile
):
    """Upload a recording and kick the transcription pipeline.

    The recording lands in B2 *before* the response is returned; the
    transcription + summary + actions stages run in the background via
    `BackgroundTasks`. The client polls `/meetings/{id}/status` to track
    progress.
    """
    content_type = file.content_type or "application/octet-stream"
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "recording"
    try:
        meeting_id, _ = init_meeting(data, filename, content_type)
    except MeetingIdError as e:
        record_upload(success=False)
        raise HTTPException(status_code=415, detail=e.detail) from None
    except RuntimeError as e:
        record_upload(success=False)
        raise HTTPException(status_code=502, detail=str(e)) from None

    background_tasks.add_task(run_pipeline, meeting_id, data)
    record_upload(success=True)
    logger.info(
        "Meeting upload accepted: id=%s size=%d type=%s",
        meeting_id,
        len(data),
        content_type,
    )
    try:
        return get_meeting(meeting_id)
    except MeetingNotFound:
        raise HTTPException(status_code=500, detail="Failed to persist meeting") from None


@router.get("/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting_endpoint(meeting_id: str):
    try:
        return get_meeting(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.delete("/meetings/{meeting_id}")
async def delete_meeting_endpoint(meeting_id: str):
    try:
        deleted, errors = remove_meeting(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to delete meeting") from None
    logger.info(
        "Meeting deleted: id=%s removed=%d errors=%d",
        meeting_id,
        len(deleted),
        len(errors),
    )
    return {"deleted": deleted, "errors": errors}


@router.get("/meetings/{meeting_id}/status", response_model=MeetingStatus | None)
async def get_status_endpoint(meeting_id: str):
    try:
        payload = get_meeting_status(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    if payload is None:
        raise HTTPException(status_code=404, detail="Status not written yet")
    return payload


@router.get("/meetings/{meeting_id}/transcript", response_model=Transcript | None)
async def get_transcript_endpoint(meeting_id: str):
    try:
        payload = get_meeting_transcript(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    if payload is None:
        raise HTTPException(status_code=404, detail="Transcript not available")
    return payload


@router.get("/meetings/{meeting_id}/summary", response_model=Summary | None)
async def get_summary_endpoint(meeting_id: str):
    try:
        payload = get_meeting_summary(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    if payload is None:
        raise HTTPException(status_code=404, detail="Summary not available")
    return payload


@router.get("/meetings/{meeting_id}/actions", response_model=ActionsBundle | None)
async def get_actions_endpoint(meeting_id: str):
    try:
        payload = get_meeting_actions(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    if payload is None:
        raise HTTPException(status_code=404, detail="Actions not available")
    return payload


@router.get("/meetings/{meeting_id}/playback")
async def get_playback_endpoint(meeting_id: str):
    try:
        url = get_playback_url(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    return {"url": url, "expires_in": 600}


@router.get("/meetings/{meeting_id}/download")
async def get_download_endpoint(meeting_id: str):
    try:
        url = get_download_url(meeting_id)
    except MeetingIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except MeetingNotFound as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    return {"url": url, "expires_in": 600}


# Re-exporting ALL_SUPPORTED so a future doctor/preflight can surface
# the accepted extension list without a backward import.
__all__ = ["ALL_SUPPORTED", "router"]
