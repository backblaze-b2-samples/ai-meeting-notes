import re
from pathlib import Path

import pytest

import main as api_main
from app.config.settings import (
    B2_PLACEHOLDER_VALUES,
    B2_REGION_PATTERN,
    B2_REQUIRED_SETTINGS,
    Settings,
)
from app.repo import b2_client

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def isolated_b2_settings(monkeypatch, tmp_path):
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


def _extract_js_strings(source: str, name: str) -> set[str]:
    match = re.search(
        rf"export const {name} = (?:new Set\()?\[(.*?)\]\)?;",
        source,
        re.DOTALL,
    )
    assert match, f"Could not find {name} in doctor env module"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _extract_js_regex(source: str, name: str) -> str:
    match = re.search(rf"export const {name} = /(.*)/;", source)
    assert match, f"Could not find {name} in doctor env module"
    return match.group(1)


def test_b2_env_contract_has_drift_guard():
    doctor_source = (REPO_ROOT / "scripts/doctor.mjs").read_text()
    doctor_env_source = (REPO_ROOT / "scripts/doctor-env.mjs").read_text()
    env_example_source = (REPO_ROOT / ".env.example").read_text()
    required_env_names = {env_name for _, env_name in B2_REQUIRED_SETTINGS}

    env_example_values = {}
    for raw in env_example_source.splitlines():
        line = raw.strip()
        if not line.startswith("B2_") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in required_env_names:
            env_example_values[key] = value

    assert api_main.B2_REQUIRED_SETTINGS == B2_REQUIRED_SETTINGS
    assert api_main.B2_PLACEHOLDER_VALUES == B2_PLACEHOLDER_VALUES
    assert 'from "./doctor-env.mjs"' in doctor_source
    assert _extract_js_strings(doctor_env_source, "REQUIRED_B2_VARS") == required_env_names
    assert _extract_js_strings(doctor_env_source, "PLACEHOLDERS") == set(B2_PLACEHOLDER_VALUES)
    assert _extract_js_regex(doctor_env_source, "B2_REGION_PATTERN") == B2_REGION_PATTERN
    assert set(env_example_values) == required_env_names
    assert set(env_example_values.values()) == set(B2_PLACEHOLDER_VALUES)

    example_region = re.search(r"^# B2_REGION=(\S+)$", env_example_source, re.MULTILINE)
    assert example_region
    assert re.fullmatch(B2_REGION_PATTERN, example_region.group(1))


def test_settings_parse_standard_b2_env_and_derive_endpoint(monkeypatch, tmp_path):
    for key in (
        "B2_REGION",
        "B2_APPLICATION_KEY_ID",
        "B2_APPLICATION_KEY",
        "B2_BUCKET_NAME",
        "B2_PUBLIC_URL_BASE",
    ):
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "B2_REGION=aa-bbbb-001",
                "B2_APPLICATION_KEY_ID=key-id",
                "B2_APPLICATION_KEY=application-key",
                "B2_BUCKET_NAME=meeting-notes",
                "B2_PUBLIC_URL_BASE=https://example.invalid/meeting-notes",
                "ASSEMBLYAI_API_KEY=assembly-key",
                "OPENAI_API_KEY=openai-key",
                "OPENAI_MODEL=gpt-test",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    assert settings.b2_bucket_name == "meeting-notes"
    assert settings.b2_application_key_id == "key-id"
    assert settings.b2_public_url_base == "https://example.invalid/meeting-notes"
    assert settings.b2_s3_endpoint == "https://s3.aa-bbbb-001.backblazeb2.com"


@pytest.mark.parametrize(
    "region",
    [
        "attacker.example/steal",
        "us-west-" + "004#x",
    ],
)
def test_b2_region_rejects_url_metacharacters_before_endpoint(region, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"B2_REGION={region}",
                "B2_APPLICATION_KEY_ID=key-id",
                "B2_APPLICATION_KEY=application-key",
                "B2_BUCKET_NAME=meeting-notes",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    with pytest.raises(ValueError, match="B2_REGION"):
        _ = settings.b2_s3_endpoint


def test_invalid_b2_region_blocks_boto3_client_creation(isolated_b2_settings, monkeypatch):
    isolated_b2_settings(_b2_env_lines(region="attacker.example/steal"))
    monkeypatch.setattr(
        b2_client.boto3,
        "client",
        lambda *_, **__: pytest.fail("boto3 client should not be created"),
    )

    with pytest.raises(ValueError, match="B2_REGION"):
        b2_client.get_s3_client()


def test_missing_b2_region_blocks_boto3_client_creation(isolated_b2_settings, monkeypatch):
    isolated_b2_settings(
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


def test_b2_s3_client_uses_bounded_botocore_config(isolated_b2_settings, monkeypatch):
    isolated_b2_settings(_b2_env_lines())
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


def test_b2_public_url_base_trailing_slash_is_normalized(isolated_b2_settings, monkeypatch):
    isolated_b2_settings(
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
