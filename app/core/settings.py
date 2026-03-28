from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # WAHA
    waha_base_url: str = "http://localhost:3000"
    waha_api_key: str = ""
    waha_session: str = "default"
    waha_webhook_secret: str = ""

    # Admin penjualan — nomor WA yang berhak kirim final order
    # Format: 6281234567890 (tanpa + atau strip)
    # Bisa multiple nomor dipisah koma: "6281234567890,6289876543210"
    admin_wa_numbers: str = ""

    # LiteLLM
    litellm_model: str = "openai/gemini-2.5-flash-lite"
    litellm_api_key: str = ""
    litellm_api_base: str = ""
    litellm_max_tokens: int = 8000
    litellm_temperature: float = 0.2

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str = ""

    # Database
    database_url: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 86400

    # Vector store
    vector_store: str = "pgvector"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # ERP
    erp_base_url: str = ""
    erp_api_key: str = ""
    erp_timeout_seconds: int = 10

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def admin_wa_list(self) -> list[str]:
        """Return list nomor admin dari config."""
        if not self.admin_wa_numbers:
            return []
        return [n.strip() for n in self.admin_wa_numbers.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
