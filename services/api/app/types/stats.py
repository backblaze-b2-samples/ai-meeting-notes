from pydantic import BaseModel


class DailyUploadCount(BaseModel):
    """One row of the dashboard activity chart.

    `duration_ms` is the sum of recording durations for meetings uploaded
    on that date — zero when the recordings have no extracted duration yet
    (e.g., very-large files for which mutagen produced nothing).
    """

    date: str
    uploads: int
    duration_ms: int = 0


class UploadStats(BaseModel):
    """Dashboard metrics for the Meetings sample.

    `total_files` / `total_size_*` cover everything in the bucket so the
    full-bucket explorer keeps its banner working. The meeting-specific
    aggregates (`total_meetings`, `total_duration_ms`, `open_action_items`,
    `meetings_by_state`) drive the dashboard cards.
    """

    total_files: int
    total_size_bytes: int
    total_size_human: str
    uploads_today: int
    total_downloads: int
    # Meeting-aware aggregates
    total_meetings: int = 0
    total_duration_ms: int = 0
    meetings_size_bytes: int = 0
    meetings_size_human: str = "0 B"
    open_action_items: int = 0
    # Sparse map of pipeline state -> count, e.g. {"done": 12, "transcribing": 1}.
    meetings_by_state: dict[str, int] = {}
