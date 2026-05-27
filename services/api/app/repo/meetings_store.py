"""B2 layout for the meeting bundle.

Every meeting lives under a single per-meeting prefix:

    meetings/<meeting-id>/
      recording.<ext>
      status.json
      transcript.json
      summary.json
      actions.json

This module owns the S3 reads and writes for that layout. Boto3 stays
inside `repo/` — service-layer callers never touch the SDK. Each writer
returns nothing (the artifact is canonical once it lands in B2); each
reader returns the raw JSON dict (callers in service/ shape them into
Pydantic models). Missing artifacts return None rather than raising —
the pipeline is async and an earlier stage having not yet written the
later artifact is the common case, not an error.
"""

from __future__ import annotations

import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from botocore.exceptions import ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client

MEETINGS_PREFIX = "meetings/"

# Meeting IDs are URL-safe slugs. The service layer assigns them at upload
# time and writes them into every key under the prefix; this regex is the
# canonical shape and is reused for path-traversal rejection.
MEETING_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")

# Canonical artifact filenames inside a meeting's prefix.
STATUS_KEY = "status.json"
TRANSCRIPT_KEY = "transcript.json"
SUMMARY_KEY = "summary.json"
ACTIONS_KEY = "actions.json"


def meeting_prefix(meeting_id: str) -> str:
    """Return the canonical S3 prefix for a meeting (with trailing slash)."""
    return f"{MEETINGS_PREFIX}{meeting_id}/"


def recording_key(meeting_id: str, ext: str) -> str:
    """Return the canonical key for a meeting's recording.

    `ext` is the lowercase file extension *without* the dot. We accept
    audio and video extensions — the meetings sample is upload-only and
    the pipeline accepts whatever the transcription provider supports.
    """
    ext = (ext or "bin").lstrip(".").lower()
    return f"{meeting_prefix(meeting_id)}recording.{ext}"


def artifact_key(meeting_id: str, artifact: str) -> str:
    """Return the canonical key for one of the JSON artifacts."""
    return f"{meeting_prefix(meeting_id)}{artifact}"


def put_recording(
    meeting_id: str, data: bytes, ext: str, content_type: str
) -> str:
    """Write the recording. Returns the resolved key.

    Raises RuntimeError on S3 failure so callers can mark the pipeline
    `failed` without reaching for boto3 themselves.
    """
    key = recording_key(meeting_id, ext)
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=io.BytesIO(data),
            ContentType=content_type,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 recording upload failed for '{key}': {e}") from e
    return key


def put_artifact(meeting_id: str, artifact: str, payload: dict) -> str:
    """Write one of the JSON artifacts. Returns the resolved key."""
    key = artifact_key(meeting_id, artifact)
    body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=io.BytesIO(body),
            ContentType="application/json",
        )
    except ClientError as e:
        raise RuntimeError(f"B2 artifact write failed for '{key}': {e}") from e
    return key


def get_artifact(meeting_id: str, artifact: str) -> dict | None:
    """Read a JSON artifact, or None when the object doesn't exist yet."""
    key = artifact_key(meeting_id, artifact)
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise
    return json.loads(response["Body"].read().decode("utf-8"))


def head_recording(meeting_id: str) -> dict | None:
    """HEAD the recording. Returns the raw S3 response or None on 404.

    We search the meeting prefix and return the first `recording.*` we
    find — the upload path picks the extension, so the listing layer
    doesn't need to know which one was used.
    """
    client = get_s3_client()
    try:
        response = client.list_objects_v2(
            Bucket=settings.b2_bucket_name,
            Prefix=meeting_prefix(meeting_id) + "recording.",
            MaxKeys=5,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for '{meeting_id}': {e}") from e
    contents = response.get("Contents") or []
    for obj in contents:
        return {
            "Key": obj["Key"],
            "Size": obj["Size"],
            "LastModified": obj["LastModified"],
        }
    return None


def list_meetings(max_keys: int = 10_000) -> list[dict]:
    """List recording objects across every meeting.

    Returns dicts of {Key, Size, LastModified} so the service layer can
    derive meeting rows without HEADing every object. We filter to keys
    that look like `meetings/<id>/recording.<ext>` — status / transcript /
    summary / actions JSONs are excluded from the listing.
    """
    client = get_s3_client()
    contents: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": MEETINGS_PREFIX,
        "MaxKeys": min(max_keys, 1000),
    }
    fetched = 0
    try:
        while fetched < max_keys:
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                # Match `meetings/<id>/recording.<ext>` exactly.
                rel = key[len(MEETINGS_PREFIX):]
                if "/" not in rel:
                    continue
                _id, _, tail = rel.partition("/")
                if tail.startswith("recording.") and "/" not in tail:
                    contents.append(obj)
                    fetched += 1
                    if fetched >= max_keys:
                        break
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 meetings list failed: {e}") from e
    return contents


def list_summary_keys(max_keys: int = 10_000) -> list[str]:
    """List every `summary.json` key — used by search."""
    client = get_s3_client()
    keys: list[str] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": MEETINGS_PREFIX,
        "MaxKeys": min(max_keys, 1000),
    }
    try:
        while len(keys) < max_keys:
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                if obj["Key"].endswith("/" + SUMMARY_KEY):
                    keys.append(obj["Key"])
                    if len(keys) >= max_keys:
                        break
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 summary key listing failed: {e}") from e
    return keys


def get_artifacts_parallel(
    meeting_ids: list[str], artifact: str, max_workers: int = 10
) -> dict[str, dict | None]:
    """Fetch one JSON artifact per meeting in parallel. Missing -> None."""
    if not meeting_ids:
        return {}

    def _one(mid: str) -> tuple[str, dict | None]:
        return mid, get_artifact(mid, artifact)

    out: dict[str, dict | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for mid, payload in pool.map(_one, meeting_ids):
            out[mid] = payload
    return out


def delete_meeting(meeting_id: str) -> tuple[list[str], list[dict]]:
    """Cascade-delete every object under the meeting's prefix.

    Returns `(deleted_keys, errors)`. Lists then batch-deletes via the
    S3 DeleteObjects op so a 10-artifact meeting is one round-trip, not
    ten. Errors are surfaced (not raised) so partial successes still
    update the UI.
    """
    client = get_s3_client()
    prefix = meeting_prefix(meeting_id)
    keys: list[str] = []
    try:
        kwargs = {
            "Bucket": settings.b2_bucket_name,
            "Prefix": prefix,
            "MaxKeys": 1000,
        }
        while True:
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                keys.append(obj["Key"])
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 delete listing failed for '{meeting_id}': {e}") from e

    if not keys:
        return [], []

    deleted: list[str] = []
    errors: list[dict] = []
    for i in range(0, len(keys), 1000):
        chunk = keys[i : i + 1000]
        try:
            response = client.delete_objects(
                Bucket=settings.b2_bucket_name,
                Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": False},
            )
        except ClientError as e:
            raise RuntimeError(f"B2 meeting delete failed: {e}") from e
        deleted.extend(d["Key"] for d in response.get("Deleted", []))
        for err in response.get("Errors", []):
            errors.append(
                {
                    "Key": err.get("Key", ""),
                    "Code": err.get("Code", ""),
                    "Message": err.get("Message", ""),
                }
            )
    return deleted, errors


def presign_recording_playback(key: str, expires_in: int = 600) -> str:
    """Inline-playback presigned GET (no Content-Disposition)."""
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.b2_bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign failed for '{key}': {e}") from e


def now_iso() -> str:
    """Return the current UTC time in ISO-8601 (used by `status.json`)."""
    return datetime.now(UTC).isoformat()
