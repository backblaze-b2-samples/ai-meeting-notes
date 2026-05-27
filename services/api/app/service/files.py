"""Bucket-explorer service layer.

This sample keeps the full-bucket explorer at `/files` so a developer
can see exactly what's in B2 next to the semantic Meetings view. The
explorer is generic: it lists, previews, and deletes objects regardless
of prefix. The Meetings UI is the primary surface; this is the ops view.

Dashboard stats sit here too — `get_stats()` calls into
`service/meeting.py::aggregate_for_dashboard` so the dashboard cards
reflect meeting-centric metrics (count, total transcribed minutes,
open action items) while the bucket-level totals stay accurate.
"""

import contextlib
import json
import logging
import os
import re
import tempfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from app.config import settings
from app.repo import (
    delete_file,
    delete_files_batch,
    get_file_metadata,
    get_presigned_url,
    get_upload_stats,
    list_files,
    list_meetings,
)
from app.service.meeting import aggregate_for_dashboard
from app.types import FileMetadata, UploadStats
from app.types.stats import DailyUploadCount

logger = logging.getLogger(__name__)

_DANGEROUS_KEY_RE = re.compile(r"(\.\./|/\.\.|\\|%2e%2e|%00|\x00)")
_download_lock = Lock()


def _counter_path() -> Path:
    """Resolve the counter file path relative to the api service root."""
    p = Path(settings.download_count_file)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p


def _load_download_count() -> int:
    try:
        with open(_counter_path()) as f:
            return int(json.load(f).get("count", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return 0


def _save_download_count(count: int) -> None:
    path = _counter_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"count": count}, f)
            os.replace(tmp, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
    except OSError as e:
        logger.warning("Failed to persist download counter: %s", e)


_download_count = _load_download_count()


def _record_download() -> None:
    global _download_count
    with _download_lock:
        _download_count += 1
        _save_download_count(_download_count)


def get_download_count() -> int:
    with _download_lock:
        return _download_count


class FileKeyError(Exception):
    """Raised when a file key is invalid."""

    def __init__(self, detail: str = "Invalid file key"):
        self.detail = detail
        super().__init__(detail)


class FileNotFoundError(Exception):
    """Raised when a file is not found."""

    def __init__(self, detail: str = "File not found"):
        self.detail = detail
        super().__init__(detail)


def validate_key(key: str) -> None:
    """Reject empty keys and keys that contain path-traversal patterns."""
    if not key:
        raise FileKeyError()
    if _DANGEROUS_KEY_RE.search(key.lower()):
        raise FileKeyError()


def get_files(prefix: str = "", limit: int = 100) -> list[FileMetadata]:
    if limit < 1 or limit > 1000:
        raise ValueError("Limit must be between 1 and 1000")
    files = list_files(prefix=prefix, max_keys=1000)
    files.sort(key=lambda f: f.uploaded_at, reverse=True)
    return files[:limit]


def get_stats() -> UploadStats:
    """Bucket totals + meeting-centric dashboard aggregates."""
    data = get_upload_stats()
    data["total_downloads"] = get_download_count()
    meetings = aggregate_for_dashboard()
    data["total_meetings"] = meetings["total_meetings"]
    data["total_duration_ms"] = meetings["total_duration_ms"]
    data["meetings_size_bytes"] = meetings["meetings_size_bytes"]
    data["meetings_size_human"] = meetings["meetings_size_human"]
    data["open_action_items"] = meetings["open_action_items"]
    data["meetings_by_state"] = meetings["meetings_by_state"]
    return UploadStats(**data)


def get_file(key: str) -> FileMetadata:
    validate_key(key)
    metadata = get_file_metadata(key)
    if not metadata:
        raise FileNotFoundError()
    return metadata


def get_preview_url(key: str) -> str:
    """Return a presigned URL without recording a download."""
    validate_key(key)
    metadata = get_file_metadata(key)
    if not metadata:
        raise FileNotFoundError()
    return get_presigned_url(key, filename=metadata.filename)


def get_download_url(key: str) -> str:
    """Return a presigned URL and record the event as a download."""
    url = get_preview_url(key)
    _record_download()
    return url


def remove_file(key: str) -> None:
    """Validate key and delete the file. Raises RuntimeError on B2 failure."""
    validate_key(key)
    delete_file(key)


def bulk_remove_files(keys: list[str]) -> tuple[list[str], list[dict]]:
    """Validate each key and batch-delete via S3 DeleteObjects.

    Returns `(deleted_keys, errors)`. Every malformed key short-circuits
    the whole batch with FileKeyError. Per-object S3 errors come back in
    `errors` so the UI can show partial success.
    """
    if not keys:
        raise FileKeyError("No keys provided")
    if len(keys) > 1000:
        raise FileKeyError("Cannot delete more than 1000 keys per request")
    seen: set[str] = set()
    cleaned: list[str] = []
    for k in keys:
        validate_key(k)
        if k not in seen:
            seen.add(k)
            cleaned.append(k)
    return delete_files_batch(cleaned)


def get_upload_activity(days: int = 7) -> list[DailyUploadCount]:
    """Return daily meeting-upload counts for the last N days.

    Meetings only — the dashboard trend line is "meetings recorded per
    day", not every file in the bucket. `list_meetings` already filters
    to recording.* keys, so the count is one row per meeting.
    """
    today = datetime.now(UTC).date()
    cutoff = today - timedelta(days=days - 1)

    raw = list_meetings(max_keys=10_000)
    in_window = [o for o in raw if o["LastModified"].date() >= cutoff]

    counts: dict[str, int] = defaultdict(int)
    for o in in_window:
        d = o["LastModified"].date().isoformat()
        counts[d] += 1

    return [
        DailyUploadCount(
            date=(cutoff + timedelta(days=i)).isoformat(),
            uploads=counts.get((cutoff + timedelta(days=i)).isoformat(), 0),
            duration_ms=0,
        )
        for i in range(days)
    ]
