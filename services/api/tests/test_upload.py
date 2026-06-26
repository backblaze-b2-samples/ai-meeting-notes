"""Regression tests for the legacy upload route."""

import json
import logging

import pytest

from app.config import settings
from main import app


async def _upload_errors_total(client) -> int:
    response = await client.get("/metrics")
    assert response.status_code == 200
    for line in response.text.splitlines():
        if line.startswith("upload_errors_total "):
            return int(line.rsplit(" ", 1)[1])
    raise AssertionError("upload_errors_total metric not found")


async def _post_upload_with_content_length(
    header: str | None,
    file_data: bytes = b"audio",
) -> tuple[int, dict]:
    boundary = "pytest-upload-boundary"
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="meeting.mp3"\r\n'
        "Content-Type: audio/mpeg\r\n\r\n"
    ).encode()
    suffix = f"\r\n--{boundary}--\r\n".encode()
    body = prefix + file_data + suffix
    sent_body = False
    messages = []
    headers = [
        (b"host", b"test"),
        (
            b"content-type",
            f"multipart/form-data; boundary={boundary}".encode("ascii"),
        ),
    ]
    if header is not None:
        headers.insert(1, (b"content-length", header.encode("ascii")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }

    async def receive():
        nonlocal sent_body
        if sent_body:
            return {"type": "http.disconnect"}
        sent_body = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)

    status = next(
        message["status"] for message in messages if message["type"] == "http.response.start"
    )
    payload = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status, json.loads(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content_length",
    ["bad-value", "+5", " 5", "5 ", "1_000", "-0", "-1"],
)
async def test_upload_rejects_invalid_content_length(
    client, caplog, content_length
):
    before_errors = await _upload_errors_total(client)
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="app.runtime.upload"):
        status, payload = await _post_upload_with_content_length(content_length)

    after_errors = await _upload_errors_total(client)
    assert status == 400
    assert payload == {"detail": "Invalid Content-Length header"}
    assert after_errors == before_errors + 1
    assert "Upload rejected: Invalid Content-Length header" in caplog.text


@pytest.mark.asyncio
async def test_upload_rejects_very_large_content_length(client, caplog):
    before_errors = await _upload_errors_total(client)
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="app.runtime.upload"):
        status, payload = await _post_upload_with_content_length("9" * 5000)

    after_errors = await _upload_errors_total(client)
    assert status == 413
    assert payload["detail"].startswith("File too large. Max size:")
    assert after_errors == before_errors + 1
    assert "Upload rejected: File too large." in caplog.text


@pytest.mark.asyncio
async def test_upload_records_streamed_file_size_rejection(
    client, caplog, monkeypatch
):
    monkeypatch.setattr(settings, "max_file_size", 3)
    before_errors = await _upload_errors_total(client)
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="app.runtime.upload"):
        status, payload = await _post_upload_with_content_length(
            None,
            file_data=b"audio",
        )

    after_errors = await _upload_errors_total(client)
    assert status == 413
    assert payload == {"detail": "File too large. Max size: 3.0 B"}
    assert after_errors == before_errors + 1
    assert "Upload rejected: File too large. Max size: 3.0 B" in caplog.text
