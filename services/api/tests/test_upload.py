"""Regression tests for the legacy upload route."""

import json
import logging

import pytest

from main import app


async def _upload_errors_total(client) -> int:
    response = await client.get("/metrics")
    assert response.status_code == 200
    for line in response.text.splitlines():
        if line.startswith("upload_errors_total "):
            return int(line.rsplit(" ", 1)[1])
    raise AssertionError("upload_errors_total metric not found")


async def _post_upload_with_content_length(header: str) -> tuple[int, dict]:
    boundary = "pytest-upload-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="meeting.mp3"\r\n'
        "Content-Type: audio/mpeg\r\n\r\n"
        "audio\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    sent_body = False
    messages = []

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-length", header.encode("ascii")),
            (
                b"content-type",
                f"multipart/form-data; boundary={boundary}".encode("ascii"),
            ),
        ],
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
