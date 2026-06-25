from app.config.settings import Settings


def test_settings_ignore_provider_specific_env_keys(monkeypatch, tmp_path):
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
                "B2_REGION=region-test",
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
    assert settings.b2_s3_endpoint == "https://s3.region-test.backblazeb2.com"
