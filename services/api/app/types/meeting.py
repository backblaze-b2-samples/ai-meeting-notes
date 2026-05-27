"""Pydantic models for the meeting pipeline.

The shape of a "meeting" is a bundle of artifacts under a single B2 prefix:

    meetings/<meeting-id>/
      recording.<ext>
      status.json
      transcript.json
      summary.json
      actions.json

Each artifact has its own model. `Meeting` is the listing-shape row — the
union of fields you can derive from the recording HEAD plus the latest
`status.json`. The full transcript / summary / actions live in their own
GET endpoints so the meeting card stays lightweight.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

PipelineStage = Literal["upload", "asr", "summary", "actions"]
StageStatus = Literal["pending", "running", "done", "failed", "skipped"]
MeetingState = Literal["queued", "transcribing", "summarizing", "done", "failed"]


class StageState(BaseModel):
    """Per-stage status inside `status.json`."""

    status: StageStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class MeetingStatus(BaseModel):
    """The persisted `status.json` for a meeting.

    Written first at upload time with `state=queued` so the UI poll always
    finds something. Each pipeline stage rewrites it before producing its
    artifact so the UI can show progress without reading large artifacts.
    """

    meeting_id: str
    state: MeetingState
    stages: dict[PipelineStage, StageState] = {}
    error: str | None = None
    updated_at: datetime
    transcription_provider: str | None = None
    llm_model: str | None = None


class SpeakerTurn(BaseModel):
    """A contiguous run by one speaker within the transcript."""

    speaker: str
    start_ms: int
    end_ms: int
    text: str


class TranscriptSegment(BaseModel):
    """One ASR segment (utterance-grain, smaller than a SpeakerTurn)."""

    id: str
    speaker: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


class Transcript(BaseModel):
    """The persisted `transcript.json` for a meeting."""

    meeting_id: str
    language: str | None = None
    duration_ms: int | None = None
    segments: list[TranscriptSegment] = []
    speakers: list[str] = []
    provider: str
    generated_at: datetime


class Summary(BaseModel):
    """The persisted `summary.json` for a meeting.

    `model` is the model identifier returned by the LLM provider, useful
    for showing "summarized by claude-haiku-4-5" in the UI without baking
    the env value into the response.
    """

    meeting_id: str
    summary: str
    decisions: list[str] = []
    topics: list[str] = []
    model: str
    generated_at: datetime


class ActionItem(BaseModel):
    """A single extracted action item.

    `source_segment_ids` lets the UI jump back to where the item came from
    in the transcript. `status` is client-side state — the server stores
    whatever the client wrote, no business rules.
    """

    id: str
    text: str
    owner: str | None = None
    due: str | None = None
    status: Literal["open", "done", "dismissed"] = "open"
    source_segment_ids: list[str] = []


class ActionsBundle(BaseModel):
    """The persisted `actions.json` for a meeting."""

    meeting_id: str
    items: list[ActionItem] = []
    model: str
    generated_at: datetime


class Meeting(BaseModel):
    """A meeting row for the Meetings list and detail page header.

    Built from the recording's HEAD plus the latest `status.json`. The
    heavy artifacts (transcript / summary / actions) ride on their own
    endpoints so listings stay cheap.
    """

    meeting_id: str
    recording_key: str
    filename: str
    size_bytes: int
    size_human: str
    content_type: str
    created_at: datetime
    duration_ms: int | None = None
    speaker_count: int | None = None
    summary_excerpt: str | None = None
    state: MeetingState = "queued"
    error: str | None = None
