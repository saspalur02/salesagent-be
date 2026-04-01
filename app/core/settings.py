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

    # Admin penjualan
    admin_wa_numbers: str = ""

    # LiteLLM (chat)
    litellm_model: str = "openai/gemini-2.5-flash"
    litellm_api_key: str = ""
    litellm_api_base: str = ""
    litellm_max_tokens: int = 8000
    litellm_temperature: float = 0.2

    # Embedding provider: "huggingface" atau "litellm"
    embedding_provider: str = "litellm"

    # LiteLLM embedding config
    embedding_model: str = "gemini/gemini-embedding-001"
    embedding_api_base: str = ""
    embedding_api_key: str = ""

    # Database lokal (AI Agent)
    database_url: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 86400

    # pgvector
    pgvector_url: str = ""

    # ERP Database Server 1 (mstr.toko + mstr.stock)
    erp_db_url: str = ""

    # ERP Database Server 2 (batch.rekapstocktoday)
    erp_batch_db_url: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def admin_wa_list(self) -> list[str]:
        if not self.admin_wa_numbers:
            return []
        return [n.strip() for n in self.admin_wa_numbers.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
