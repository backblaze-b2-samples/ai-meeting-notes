from app.config.settings import Settings
from app.repo.b2_client import SAMPLE_USER_AGENT


def test_settings_use_standard_b2_env_names(monkeypatch, tmp_path):
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
                "B2_REGION=test-region-001",
                "B2_APPLICATION_KEY_ID=application-key-id",
                "B2_APPLICATION_KEY=application-key",
                "B2_BUCKET_NAME=meeting-notes",
                "B2_PUBLIC_URL_BASE=https://cdn.example/meeting-notes",
                "ASSEMBLYAI_API_KEY=assembly-key",
                "OPENAI_API_KEY=openai-key",
                "OPENAI_MODEL=gpt-test",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    assert settings.b2_application_key_id == "application-key-id"
    assert settings.b2_bucket_name == "meeting-notes"
    assert settings.b2_endpoint_url == "https://s3.test-region-001.backblazeb2.com"
    assert settings.b2_public_url_base == "https://cdn.example/meeting-notes"


def test_s3_user_agent_identifies_sample_suite():
    assert "b2ai-ai-meeting-notes" in SAMPLE_USER_AGENT
    assert "backblaze-b2-samples" in SAMPLE_USER_AGENT
