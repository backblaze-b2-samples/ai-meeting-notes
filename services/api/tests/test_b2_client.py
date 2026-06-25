import pytest

from app.config.settings import Settings
from app.repo import b2_client


@pytest.fixture
def isolated_b2_client_settings(monkeypatch, tmp_path):
    cached_get_s3_client = b2_client.get_s3_client

    def apply(lines: list[str]) -> Settings:
        env_file = tmp_path / ".env"
        env_file.write_text("\n".join(lines))
        settings = Settings(_env_file=env_file)
        cached_get_s3_client.cache_clear()
        monkeypatch.setattr(b2_client, "settings", settings)
        return settings

    yield apply
    cached_get_s3_client.cache_clear()


def _b2_env_lines(region: str = "aa-bbbb-001") -> list[str]:
    return [
        f"B2_REGION={region}",
        "B2_APPLICATION_KEY_ID=key-id",
        "B2_APPLICATION_KEY=application-key",
        "B2_BUCKET_NAME=meeting-notes",
    ]


def test_invalid_b2_region_blocks_boto3_client_creation(isolated_b2_client_settings, monkeypatch):
    isolated_b2_client_settings(_b2_env_lines(region="attacker.example/steal"))
    monkeypatch.setattr(
        b2_client.boto3,
        "client",
        lambda *_, **__: pytest.fail("boto3 client should not be created"),
    )

    with pytest.raises(ValueError, match="B2_REGION"):
        b2_client.get_s3_client()


def test_missing_b2_region_blocks_boto3_client_creation(isolated_b2_client_settings, monkeypatch):
    isolated_b2_client_settings(
        [
            "B2_APPLICATION_KEY_ID=key-id",
            "B2_APPLICATION_KEY=application-key",
            "B2_BUCKET_NAME=meeting-notes",
        ]
    )
    monkeypatch.setattr(
        b2_client.boto3,
        "client",
        lambda *_, **__: pytest.fail("boto3 client should not be created"),
    )

    with pytest.raises(RuntimeError, match="B2_REGION"):
        b2_client.get_s3_client()


def test_b2_s3_client_uses_bounded_botocore_config(isolated_b2_client_settings, monkeypatch):
    isolated_b2_client_settings(_b2_env_lines())
    captured = {}
    sentinel_client = object()

    def fake_boto3_client(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel_client

    monkeypatch.setattr(b2_client.boto3, "client", fake_boto3_client)

    assert b2_client.get_s3_client() is sentinel_client

    config = captured["kwargs"]["config"]
    assert captured["args"] == ("s3",)
    assert captured["kwargs"]["endpoint_url"] == "https://s3.aa-bbbb-001.backblazeb2.com"
    assert config.connect_timeout == b2_client.B2_CONNECT_TIMEOUT_SECONDS
    assert config.read_timeout == b2_client.B2_READ_TIMEOUT_SECONDS
    assert config.retries == {
        "mode": "standard",
        "total_max_attempts": b2_client.B2_TOTAL_MAX_ATTEMPTS,
    }
    assert config.signature_version == "s3v4"
    assert config.user_agent_extra == "b2ai-ai-meeting-notes (backblaze-b2-samples)"


def test_upload_file_returns_normalized_public_url(isolated_b2_client_settings, monkeypatch):
    isolated_b2_client_settings(
        [
            *_b2_env_lines(),
            "B2_PUBLIC_URL_BASE=https://cdn.example/meeting-notes/",
        ]
    )
    put_calls = []

    class FakeS3Client:
        def put_object(self, **params):
            put_calls.append(params)

    monkeypatch.setattr(b2_client, "get_s3_client", lambda: FakeS3Client())

    metadata = b2_client.upload_file(
        b"recording",
        "meetings/demo recording.mp3",
        "audio/mpeg",
    )

    assert metadata.url == ("https://cdn.example/meeting-notes/meetings/demo%20recording.mp3")
    assert put_calls[0]["Bucket"] == "meeting-notes"
