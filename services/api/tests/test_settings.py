from app.config.settings import Settings


def test_settings_ignore_provider_specific_env_keys(monkeypatch, tmp_path):
    for key in (
        "B2_ENDPOINT",
        "B2_REGION",
        "B2_KEY_ID",
        "B2_APPLICATION_KEY",
        "B2_BUCKET_NAME",
    ):
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "B2_ENDPOINT=https://example.invalid",
                "B2_REGION=us-west-004",
                "B2_KEY_ID=key-id",
                "B2_APPLICATION_KEY=application-key",
                "B2_BUCKET_NAME=meeting-notes",
                "ASSEMBLYAI_API_KEY=assembly-key",
                "OPENAI_API_KEY=openai-key",
                "OPENAI_MODEL=gpt-test",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    assert settings.b2_bucket_name == "meeting-notes"
