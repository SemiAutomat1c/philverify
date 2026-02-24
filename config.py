"""
PhilVerify — Application Settings
Loaded via pydantic-settings from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API Keys ──────────────────────────────────────────────────────────────
    news_api_key: str = ""
    google_vision_api_key: str = ""

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./philverify_dev.db"  # Dev fallback

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = ""  # Empty = disable caching

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # ── ML Models ─────────────────────────────────────────────────────────────
    ml_model_name: str = "xlm-roberta-base"
    whisper_model_size: str = "base"
    use_gpu: bool = False

    # ── Scoring Weights ───────────────────────────────────────────────────────
    ml_weight: float = 0.40
    evidence_weight: float = 0.60
    credible_threshold: float = 70.0
    fake_threshold: float = 40.0

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
