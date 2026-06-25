import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Single source of truth: repo-root .env. Anchored to this file's path so it
# resolves correctly regardless of where uvicorn is invoked from (local
# `cd services/api && uvicorn`, Docker WORKDIR, etc.).
REPO_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(REPO_ROOT_ENV)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from app.config import (  # noqa: E402
    B2_PLACEHOLDER_VALUES,
    B2_REQUIRED_SETTINGS,
    settings,
    validate_b2_region,
)
from app.runtime import files, health, meetings, metrics, search, upload  # noqa: E402

# --- Startup validation ---
# Required B2 settings are declared with empty-string defaults so that
# `Settings()` instantiation (and therefore `from main import app`) never
# raises during test collection. We instead fail fast at server startup
# with a human-readable message — uvicorn surfaces this as the first log
# line, so misconfiguration is obvious within seconds rather than turning
# into mysterious 500s on the first request.
ROLLING_B2_MIGRATION_HELP = (
    "For rolling upgrades from legacy B2 env names, add the standardized "
    "variables alongside the legacy key-id/endpoint variables before "
    "deploying this release; remove legacy variables only after old API "
    "instances are drained."
)


@asynccontextmanager
async def lifespan(_app: "FastAPI"):
    missing = [env_name for attr, env_name in B2_REQUIRED_SETTINGS if not getattr(settings, attr)]
    if missing:
        raise RuntimeError(
            "Missing required B2 configuration: "
            + ", ".join(missing)
            + f". Add them to {REPO_ROOT_ENV} (see .env.example) and restart. "
            + ROLLING_B2_MIGRATION_HELP
        )

    placeholders = [
        env_name
        for attr, env_name in B2_REQUIRED_SETTINGS
        if getattr(settings, attr) in B2_PLACEHOLDER_VALUES
    ]
    if placeholders:
        raise RuntimeError(
            "B2 configuration still has placeholder values: "
            + ", ".join(placeholders)
            + f". Edit {REPO_ROOT_ENV} with your real B2 credentials and restart."
        )

    try:
        validate_b2_region(settings.b2_region)
    except ValueError as exc:
        raise RuntimeError(f"{exc} {ROLLING_B2_MIGRATION_HELP}") from exc
    yield


# --- Structured JSON logging ---


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
# Quiet noisy libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("api")


# --- App setup ---

app = FastAPI(
    title="AI Meeting Notes API",
    description=(
        "Meeting upload, transcription pipeline (ASR + summary + action "
        "items), per-meeting bundle storage, and cross-meeting search — "
        "backed by Backblaze B2."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Optional regex (empty by default). When set, any origin matching
    # the pattern is allowed in addition to the explicit allowlist.
    allow_origin_regex=settings.api_cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Request ID + timing middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=metrics.timing_middleware)

app.include_router(health.router, tags=["health"])
app.include_router(upload.router, tags=["upload"])
app.include_router(meetings.router, tags=["meetings"])
app.include_router(search.router, tags=["search"])
app.include_router(files.router, tags=["files"])
app.include_router(metrics.router, tags=["metrics"])
