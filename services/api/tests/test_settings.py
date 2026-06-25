import pytest

from app.config.settings import Settings


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
