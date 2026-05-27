"""Pipeline executor for the meeting transcription -> summary -> actions chain.

Split out of `service/meeting.py` to keep both files under the 300-line
limit. The orchestrator in `meeting.py` calls `run_pipeline()`; that
function in turn calls into `repo/transcription.py` and `repo/llm.py`,
writing artifacts and re-stamping `status.json` between stages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.repo import (
    ACTIONS_KEY,
    STATUS_KEY,
    SUMMARY_KEY,
    TRANSCRIPT_KEY,
    put_artifact,
)
from app.repo.llm import LLMError, extract_actions, summarize
from app.repo.transcription import TranscriptionError, transcribe
from app.types import (
    ActionsBundle,
    MeetingStatus,
    StageState,
    Summary,
    Transcript,
)

logger = logging.getLogger(__name__)


def _write_status(
    meeting_id: str,
    state: str,
    stages: dict[str, StageState],
    error: str | None = None,
    provider: str | None = None,
    llm_model: str | None = None,
) -> None:
    """Serialize and persist the meeting's `status.json`."""
    payload = MeetingStatus(
        meeting_id=meeting_id,
        state=state,  # type: ignore[arg-type]
        stages={k: v for k, v in stages.items()},  # type: ignore[arg-type]
        error=error,
        updated_at=datetime.now(UTC),
        transcription_provider=provider,
        llm_model=llm_model,
    ).model_dump(mode="json")
    put_artifact(meeting_id, STATUS_KEY, payload)


def _run_asr(
    meeting_id: str,
    file_data: bytes,
    stages: dict[str, StageState],
) -> dict:
    stages["asr"] = StageState(status="running", started_at=datetime.now(UTC))
    _write_status(meeting_id, "transcribing", stages)
    try:
        tr_dict = transcribe(file_data)
    except TranscriptionError as e:
        stages["asr"] = StageState(
            status="failed", finished_at=datetime.now(UTC), error=str(e)
        )
        _write_status(meeting_id, "failed", stages, error=str(e))
        raise
    transcript = Transcript(
        meeting_id=meeting_id,
        generated_at=datetime.now(UTC),
        **{k: v for k, v in tr_dict.items() if k != "meeting_id"},
    )
    put_artifact(meeting_id, TRANSCRIPT_KEY, transcript.model_dump(mode="json"))
    stages["asr"] = StageState(status="done", finished_at=datetime.now(UTC))
    return tr_dict


def _run_summary(
    meeting_id: str,
    tr_dict: dict,
    provider: str | None,
    stages: dict[str, StageState],
) -> str | None:
    stages["summary"] = StageState(status="running", started_at=datetime.now(UTC))
    _write_status(meeting_id, "summarizing", stages, provider=provider)
    try:
        sm_dict = summarize(tr_dict)
    except LLMError as e:
        stages["summary"] = StageState(
            status="failed", finished_at=datetime.now(UTC), error=str(e)
        )
        _write_status(meeting_id, "failed", stages, error=str(e), provider=provider)
        raise
    summary = Summary(
        meeting_id=meeting_id, generated_at=datetime.now(UTC), **sm_dict
    )
    put_artifact(meeting_id, SUMMARY_KEY, summary.model_dump(mode="json"))
    stages["summary"] = StageState(status="done", finished_at=datetime.now(UTC))
    return sm_dict.get("model")


def _run_actions(
    meeting_id: str,
    tr_dict: dict,
    provider: str | None,
    llm_model: str | None,
    stages: dict[str, StageState],
) -> None:
    stages["actions"] = StageState(status="running", started_at=datetime.now(UTC))
    _write_status(
        meeting_id, "summarizing", stages, provider=provider, llm_model=llm_model
    )
    try:
        ac_dict = extract_actions(tr_dict)
    except LLMError as e:
        stages["actions"] = StageState(
            status="failed", finished_at=datetime.now(UTC), error=str(e)
        )
        _write_status(
            meeting_id,
            "failed",
            stages,
            error=str(e),
            provider=provider,
            llm_model=llm_model,
        )
        raise
    actions = ActionsBundle(
        meeting_id=meeting_id, generated_at=datetime.now(UTC), **ac_dict
    )
    put_artifact(meeting_id, ACTIONS_KEY, actions.model_dump(mode="json"))
    stages["actions"] = StageState(status="done", finished_at=datetime.now(UTC))


def _mark_running_stage_failed(
    stages: dict[str, StageState],
    error: str,
) -> None:
    for name, stage in stages.items():
        if stage.status != "running":
            continue
        stages[name] = stage.model_copy(
            update={
                "status": "failed",
                "finished_at": datetime.now(UTC),
                "error": error,
            }
        )
        return


def run_pipeline(meeting_id: str, file_data: bytes) -> None:
    """Execute ASR -> summary -> actions in sequence.

    Each stage rewrites `status.json` before doing its work. On any
    failure the meeting is marked `failed` and later stages are skipped
    rather than partially executed.
    """
    stages: dict[str, StageState] = {
        "upload": StageState(status="done"),
        "asr": StageState(status="pending"),
        "summary": StageState(status="pending"),
        "actions": StageState(status="pending"),
    }
    try:
        tr_dict = _run_asr(meeting_id, file_data, stages)
        provider = tr_dict.get("provider")
        llm_model = _run_summary(meeting_id, tr_dict, provider, stages)
        _run_actions(meeting_id, tr_dict, provider, llm_model, stages)
        _write_status(
            meeting_id, "done", stages, provider=provider, llm_model=llm_model
        )
        logger.info("Pipeline complete: meeting_id=%s", meeting_id)
    except Exception as e:
        if not any(stage.status == "failed" for stage in stages.values()):
            error = str(e) or e.__class__.__name__
            _mark_running_stage_failed(stages, error)
            try:
                _write_status(meeting_id, "failed", stages, error=error)
            except Exception:
                logger.exception(
                    "Failed to persist failed status for meeting_id=%s",
                    meeting_id,
                )
        logger.exception("Pipeline failed for meeting_id=%s", meeting_id)
        raise


def write_initial_status(meeting_id: str) -> None:
    """Persist the very first `status.json` (state=queued) at upload time."""
    stages = {
        "upload": StageState(
            status="done",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        ),
        "asr": StageState(status="pending"),
        "summary": StageState(status="pending"),
        "actions": StageState(status="pending"),
    }
    _write_status(meeting_id, "queued", stages)
