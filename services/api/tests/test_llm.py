"""Unit tests for the LLM adapter — Anthropic + OpenAI dispatch."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.repo import llm


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch):
    """Tests opt in to their provider via monkeypatch.setenv. Start clean."""
    for var in (
        "LLM_PROVIDER",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    # The client factories are lru_cached; monkeypatching the module
    # attribute below bypasses the cache, but tests that exercise the
    # real factory need a clean cache too.
    llm._anthropic_client.cache_clear()
    llm._openai_client.cache_clear()


def _fake_anthropic_client(args_by_tool: dict):
    """Build an Anthropic-shaped fake that returns the matching tool_use."""

    class _Messages:
        def create(self, *, tools, tool_choice, **_):
            name = tool_choice["name"]
            args = args_by_tool[name]
            block = SimpleNamespace(type="tool_use", name=name, input=args)
            return SimpleNamespace(content=[block])

    return SimpleNamespace(messages=_Messages())


def _fake_openai_client(args_by_name: dict):
    """Build an OpenAI-shaped fake that returns the matching json_schema body."""

    class _Completions:
        def create(self, *, response_format, **_):
            name = response_format["json_schema"]["name"]
            payload = json.dumps(args_by_name[name])
            message = SimpleNamespace(content=payload)
            choice = SimpleNamespace(message=message)
            return SimpleNamespace(choices=[choice])

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))


def _sample_transcript() -> dict:
    return {
        "segments": [
            {"id": "u00000", "speaker": "Speaker A", "text": "Ship the docs by Friday."},
            {"id": "u00001", "speaker": "Speaker B", "text": "I'll handle the deploy."},
        ]
    }


def test_summarize_openai_default(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_openai_client",
        lambda: _fake_openai_client(
            {
                llm.SUMMARY_TOOL_NAME: {
                    "summary": "Discussed shipping and deploy.",
                    "decisions": ["Ship docs Friday"],
                    "topics": ["release"],
                }
            }
        ),
    )
    out = llm.summarize(_sample_transcript())
    assert out["summary"] == "Discussed shipping and deploy."
    assert out["decisions"] == ["Ship docs Friday"]
    assert out["topics"] == ["release"]
    assert out["model"] == llm.DEFAULT_OPENAI_MODEL


def test_summarize_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(
        llm,
        "_anthropic_client",
        lambda: _fake_anthropic_client(
            {
                llm.SUMMARY_TOOL_NAME: {
                    "summary": "Discussed shipping and deploy.",
                    "decisions": ["Ship docs Friday"],
                    "topics": ["release"],
                }
            }
        ),
    )
    out = llm.summarize(_sample_transcript())
    assert out["summary"] == "Discussed shipping and deploy."
    assert out["model"] == llm.DEFAULT_ANTHROPIC_MODEL


def test_extract_actions_anthropic_handles_missing_owner_due(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(
        llm,
        "_anthropic_client",
        lambda: _fake_anthropic_client(
            {
                llm.ACTIONS_TOOL_NAME: {
                    "items": [
                        {"text": "Ship the docs.", "owner": "Alex", "due": "Friday"},
                        {"text": "Deploy the API.", "owner": None, "due": None},
                    ]
                }
            }
        ),
    )
    out = llm.extract_actions(_sample_transcript())
    assert len(out["items"]) == 2
    assert out["items"][0]["owner"] == "Alex"
    assert out["items"][0]["due"] == "Friday"
    assert out["items"][1]["owner"] is None
    assert out["items"][1]["due"] is None
    assert all(it["status"] == "open" for it in out["items"])


def test_extract_actions_openai(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_openai_client",
        lambda: _fake_openai_client(
            {
                llm.ACTIONS_TOOL_NAME: {
                    "items": [
                        {"text": "Ship the docs.", "owner": "Alex", "due": None},
                    ]
                }
            }
        ),
    )
    out = llm.extract_actions(_sample_transcript())
    assert len(out["items"]) == 1
    assert out["items"][0]["text"] == "Ship the docs."
    assert out["items"][0]["due"] is None


def test_summarize_empty_transcript_short_circuits():
    out = llm.summarize({"segments": []})
    assert out["summary"].startswith("Empty transcript")
    assert out["decisions"] == []
    assert out["topics"] == []


def test_missing_anthropic_key_raises():
    with pytest.raises(llm.LLMError, match="ANTHROPIC_API_KEY"):
        llm._anthropic_client()


def test_missing_openai_key_raises():
    with pytest.raises(llm.LLMError, match="OPENAI_API_KEY"):
        llm._openai_client()


def test_anthropic_returns_no_tool_call(monkeypatch):
    """If the provider misbehaves and skips the tool, we error loudly."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(
        llm,
        "_anthropic_client",
        lambda: SimpleNamespace(
            messages=SimpleNamespace(create=lambda **_: SimpleNamespace(content=[]))
        ),
    )
    with pytest.raises(llm.LLMError, match="did not emit"):
        llm.summarize(_sample_transcript())


def test_openai_returns_malformed_json(monkeypatch):
    bad = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: SimpleNamespace(
                    choices=[
                        SimpleNamespace(message=SimpleNamespace(content="not json{"))
                    ]
                )
            )
        )
    )
    monkeypatch.setattr(llm, "_openai_client", lambda: bad)
    with pytest.raises(llm.LLMError, match="malformed JSON"):
        llm.summarize(_sample_transcript())
