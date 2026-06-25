import re

from pydantic_settings import BaseSettings

B2_REQUIRED_SETTINGS = (
    ("b2_application_key_id", "B2_APPLICATION_KEY_ID"),
    ("b2_application_key", "B2_APPLICATION_KEY"),
    ("b2_bucket_name", "B2_BUCKET_NAME"),
    ("b2_region", "B2_REGION"),
)
B2_PLACEHOLDER_VALUES = frozenset(
    {
        "your_b2_region",
        "your_application_key_id",
        "your_application_key",
        "your-bucket-name",
    }
)
B2_REGION_PATTERN = r"^[a-z]{2}(?:-[a-z]+)+-\d{3}$"
B2_REGION_RE = re.compile(B2_REGION_PATTERN)


def validate_b2_region(region: str) -> str:
    if not B2_REGION_RE.fullmatch(region):
        raise ValueError(
            "B2_REGION must match Backblaze's region format: lowercase "
            "letters and hyphens followed by a three-digit shard."
        )
    return region


class Settings(BaseSettings):
    b2_region: str = ""
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_public_url_base: str = ""

    api_port: int = 8000
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Small durable counters (downloads, etc). Point at a persistent
    # volume in production if you care about surviving restarts.
    download_count_file: str = "data/download_count.json"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def b2_s3_endpoint(self) -> str | None:
        if not self.b2_region:
            return None
        region = validate_b2_region(self.b2_region)
        return f"https://s3.{region}.backblazeb2.com"


settings = Settings()
