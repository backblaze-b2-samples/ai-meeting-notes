"""LLM adapter for meeting summary + action-item extraction.

`summarize` / `extract_actions` dispatch on `LLM_PROVIDER`: `openai`
(default, GPT JSON-schema strict mode) or `anthropic` (Claude tool-use).
Clients are built lazily so a missing provider key fails the pipeline
stage with a clear message instead of crashing the process at import.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
MAX_TRANSCRIPT_CHARS = 60_000


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns malformed output."""


def _provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").strip().lower() or "openai"


def _model() -> str:
    if _provider() == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_ANTHROPIC_MODEL
    return os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL


@functools.lru_cache(maxsize=1)
def _anthropic_client():
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise LLMError(
            "anthropic package not installed — `pip install anthropic`"
        ) from e
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=key)


@functools.lru_cache(maxsize=1)
def _openai_client():
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError(
            "openai package not installed — `pip install openai`"
        ) from e
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise LLMError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=key)


def _transcript_text(transcript: dict) -> str:
    """Render a Transcript dict into a speaker-tagged string, truncated to
    `MAX_TRANSCRIPT_CHARS` so a long meeting can't blow the context window
    (the lossy-truncation is documented in `docs/RELIABILITY.md`)."""
    lines: list[str] = []
    for seg in transcript.get("segments", []):
        speaker = seg.get("speaker") or "Speaker"
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"[{speaker}] {text}")
    body = "\n".join(lines)
    if len(body) > MAX_TRANSCRIPT_CHARS:
        body = body[:MAX_TRANSCRIPT_CHARS] + "\n[...transcript truncated...]"
    return body


# Strict JSON Schemas reused by both providers. OpenAI strict mode
# requires every property in `required` and `additionalProperties: false`
# at every object level; optional fields are expressed as nullable.
# Anthropic tool-use accepts the same schema fine.
SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": "3-6 sentences describing what the meeting was about and what was discussed.",
        },
        "decisions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific decisions made in the meeting. Empty array if none.",
        },
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short topic labels (1-3 words each) covering what was discussed.",
        },
    },
    "required": ["summary", "decisions", "topics"],
}

ACTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "What needs to be done. One sentence.",
                    },
                    "owner": {
                        "type": ["string", "null"],
                        "description": "Who is responsible. Null if not stated.",
                    },
                    "due": {
                        "type": ["string", "null"],
                        "description": "When it is due (free-form, e.g. 'Friday'). Null if not stated.",
                    },
                },
                "required": ["text", "owner", "due"],
            },
        },
    },
    "required": ["items"],
}

SUMMARY_TOOL_NAME = "record_meeting_summary"
SUMMARY_TOOL_DESC = (
    "Record the structured summary, decisions, and topics for the meeting."
)
ACTIONS_TOOL_NAME = "record_action_items"
ACTIONS_TOOL_DESC = "Record the action items extracted from the meeting transcript."


def _call_openai(prompt: str, name: str, schema: dict) -> dict[str, Any]:
    client = _openai_client()
    response = client.chat.completions.create(
        model=_model(),
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": schema},
        },
    )
    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise LLMError(f"OpenAI returned no content for '{name}'")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMError(f"OpenAI returned malformed JSON for '{name}': {e}") from e
    if not isinstance(parsed, dict):
        raise LLMError(f"OpenAI returned non-object JSON for '{name}'")
    return parsed


def _call_anthropic(
    prompt: str, name: str, schema: dict, description: str
) -> dict[str, Any]:
    client = _anthropic_client()
    response = client.messages.create(
        model=_model(),
        max_tokens=2048,
        tools=[{"name": name, "description": description, "input_schema": schema}],
        tool_choice={"type": "tool", "name": name},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == name:
            args = block.input
            if isinstance(args, dict):
                return args
    raise LLMError(f"Anthropic did not emit the expected '{name}' tool call")


def _structured_call(
    prompt: str, name: str, schema: dict, description: str
) -> dict[str, Any]:
    """Run a structured-output call against the selected provider."""
    if _provider() == "anthropic":
        return _call_anthropic(prompt, name, schema, description)
    # Default to OpenAI for any other value — loud errors come from
    # the SDK key check, not a quiet fallthrough.
    return _call_openai(prompt, name, schema)


def summarize(transcript: dict) -> dict:
    """Generate the structured summary for a transcript dict.

    Returns a dict in the shape `Summary` expects (minus `meeting_id`
    and `generated_at`, which the service layer fills in).
    """
    body = _transcript_text(transcript)
    if not body.strip():
        return {
            "summary": "Empty transcript — nothing to summarize.",
            "decisions": [],
            "topics": [],
            "model": _model(),
        }
    prompt = (
        "You are summarizing a recorded meeting. Use the speaker-tagged "
        "transcript below to produce a concise summary, the list of "
        "explicit decisions made, and short topic labels.\n\n"
        f"TRANSCRIPT:\n{body}"
    )
    logger.info("Summary started: provider=%s model=%s chars=%d", _provider(), _model(), len(body))
    args = _structured_call(prompt, SUMMARY_TOOL_NAME, SUMMARY_SCHEMA, SUMMARY_TOOL_DESC)
    return {
        "summary": (args.get("summary") or "").strip(),
        "decisions": [
            d.strip() for d in (args.get("decisions") or []) if d and d.strip()
        ],
        "topics": [t.strip() for t in (args.get("topics") or []) if t and t.strip()],
        "model": _model(),
    }


def _segment_ids_for(text: str, transcript: dict) -> list[str]:
    """Substring-overlap heuristic for deep-linking an action item back to
    transcript segments. v2 (embedding search) is tracked in exec-plans/."""
    needle = text.lower().strip()
    if not needle:
        return []
    hits: list[str] = []
    for seg in transcript.get("segments", []):
        if seg.get("text") and needle[:32] in seg["text"].lower():
            hits.append(seg["id"])
            if len(hits) >= 3:
                break
    return hits


def extract_actions(transcript: dict) -> dict:
    """Extract action items as a dict shaped for `ActionsBundle`."""
    body = _transcript_text(transcript)
    if not body.strip():
        return {"items": [], "model": _model()}
    prompt = (
        "You are extracting action items from a recorded meeting. An "
        "action item is a concrete thing someone agreed to do. Include "
        "owner and due-date only when explicitly stated; otherwise leave "
        "them null.\n\n"
        f"TRANSCRIPT:\n{body}"
    )
    logger.info("Actions started: provider=%s model=%s chars=%d", _provider(), _model(), len(body))
    args = _structured_call(prompt, ACTIONS_TOOL_NAME, ACTIONS_SCHEMA, ACTIONS_TOOL_DESC)
    items_in = args.get("items") or []
    items: list[dict] = []
    for raw in items_in:
        text = (raw.get("text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "id": f"a-{uuid.uuid4().hex[:10]}",
                "text": text,
                "owner": (raw.get("owner") or "").strip() or None,
                "due": (raw.get("due") or "").strip() or None,
                "status": "open",
                "source_segment_ids": _segment_ids_for(text, transcript),
            }
        )
    return {"items": items, "model": _model()}
